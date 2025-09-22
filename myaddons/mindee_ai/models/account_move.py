import base64
import json
import logging
import subprocess
import re
from datetime import datetime

from odoo import models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    mindee_local_response = fields.Text(
        string="Réponse OCR JSON (Tesseract)",
        readonly=True,
        store=True,
    )

    # ----------- 🔧 Helpers -----------

    def _normalize_date(self, date_str):
        """Convertit une chaîne en date si possible."""
        if not date_str:
            return None
        date_str = date_str.strip().replace("-", "/").replace(".", "/")
        for fmt in ("%d/%m/%Y", "%Y/%m/%d", "%d/%m/%y"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except Exception:
                continue
        return None

    def _extract_date_from_phrases(self, phrases):
        date_re = re.compile(r"(?<!\d)(\d{2}[/-]\d{2}[/-]\d{4})(?!\d)")
        for ph in phrases or []:
            m = date_re.search(ph)
            if m:
                return self._normalize_date(m.group(1))
        return None

    def _extract_invoice_number_from_phrases(self, phrases):
        inv_ctx = re.compile(
            r"facture\s*(?:n[°o]|num(?:éro)?|#)?\s*[:\-]?\s*([A-Z0-9\-_/\.]+)",
            re.IGNORECASE,
        )
        is_date = re.compile(r"^\d{2}[/-]\d{2}[/-]\d{4}$")
        is_phone = re.compile(r"^(?:0[1-9](?:\s?\d{2}){4}|0[1-9]\d{8})$")

        # 1) Ligne contextuelle « FACTURE … »
        for ph in phrases or []:
            low = ph.lower()
            if "tél" in low or "tel" in low:
                continue
            m = inv_ctx.search(ph)
            if m:
                cand = m.group(1).strip().strip(":;.,|-")
                if not is_date.match(cand) and not is_phone.match(cand):
                    return cand

        # 2) Fallback
        for ph in phrases or []:
            low = ph.lower()
            if "tél" in low or "tel" in low:
                continue
            if "facture" in low:
                after = ph.split(":", 1)[-1] if ":" in ph else ph.split(None, 1)[-1]
                for tok in re.split(r"\s+", after):
                    tok = tok.strip().strip(".,;:|-/")
                    if not tok:
                        continue
                    if is_date.match(tok) or is_phone.match(tok):
                        continue
                    if re.search(r"[A-Za-z0-9]", tok):
                        return tok
        return None

    def _extract_net_a_payer(self, phrases):
        nap_re = re.compile(
            r"net\s*(?:à|a)\s*payer[^0-9]*([0-9]+(?:[.,]\d{1,2})?)", re.IGNORECASE
        )
        for ph in phrases or []:
            m = nap_re.search(ph)
            if m:
                try:
                    return float(m.group(1).replace(",", "."))
                except Exception:
                    pass
        return None

    def _extract_total_ht(self, phrases):
        ht_re = re.compile(r"(?:total\s+net\s+h\.?t\.?|base\s+ht)[^0-9]*([0-9]+(?:[.,]\d{1,2})?)", re.IGNORECASE)
        for ph in phrases or []:
            m = ht_re.search(ph)
            if m:
                try:
                    return float(m.group(1).replace(",", "."))
                except Exception:
                    pass
        return None

    def _extract_tva(self, phrases):
        tva_re = re.compile(r"tva[^0-9]*([0-9]+(?:[.,]\d{1,2})?)", re.IGNORECASE)
        for ph in phrases or []:
            m = tva_re.search(ph)
            if m:
                try:
                    return float(m.group(1).replace(",", "."))
                except Exception:
                    pass
        return None

    # ----------- 🚀 Action OCR -----------

    def action_ocr_fetch(self):
        for move in self:
            # 1. Récupérer le PDF attaché
            pdf_attachments = move.attachment_ids.filtered(
                lambda a: a.mimetype == "application/pdf"
            )[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = pdf_attachments[0]

            file_path = "/tmp/ocr_temp_file.pdf"
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(attachment.datas))

            # 2. Appel du script Tesseract runner
            venv_python = "/data/odoo/odoo18-venv/bin/python3"
            tesseract_script_path = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/scripts/tesseract_runner.py"

            try:
                result = subprocess.run(
                    [venv_python, tesseract_script_path, file_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=180,
                    check=True,
                    encoding="utf-8",
                )
                ocr_json = result.stdout.strip()

                try:
                    ocr_data = json.loads(ocr_json)
                except json.JSONDecodeError:
                    raise UserError(
                        f"OCR n'a pas renvoyé de JSON valide pour {attachment.name}.\n\n"
                        f"Sortie brute (500 premiers caractères) :\n{ocr_json[:500]}"
                    )

            except subprocess.CalledProcessError as e:
                _logger.error("OCR failed for %s", attachment.name)
                raise UserError(
                    f"Erreur OCR avec Tesseract :\n\nSTDERR:\n{e.stderr}\n\nSTDOUT:\n{e.stdout}"
                )
            except Exception as e:
                _logger.error("Unexpected OCR error for %s: %s", attachment.name, str(e))
                raise UserError(f"Erreur OCR avec Tesseract : {e}")

            # 3. Sauvegarder la réponse JSON
            move.mindee_local_response = json.dumps(
                ocr_data, indent=2, ensure_ascii=False
            )

            self.env["ir.attachment"].create({
                "name": f"OCR_{attachment.name}.json",
                "res_model": "account.move",
                "res_id": move.id,
                "type": "binary",
                "mimetype": "application/json",
                "datas": base64.b64encode(json.dumps(ocr_data, indent=2).encode("utf-8")),
            })

            # 4. Exploiter les phrases
            pages = ocr_data.get("pages", [])
            phrases = pages[0].get("phrases", []) if pages else []

            invoice_date = self._extract_date_from_phrases(phrases)
            invoice_number = self._extract_invoice_number_from_phrases(phrases)
            amount_total = self._extract_net_a_payer(phrases)
            total_ht = self._extract_total_ht(phrases)
            total_tva = self._extract_tva(phrases)

            vals = {
                "invoice_date": invoice_date,
                "ref": invoice_number,
                "amount_total": amount_total,
            }

            # optionnel : stocker HT et TVA dans des champs custom
            if total_ht:
                vals["amount_untaxed"] = total_ht
            if total_tva:
                vals["amount_tax"] = total_tva

            try:
                move.write(vals)
            except Exception as e:
                raise UserError(f"Erreur d’écriture dans la facture : {e}")

        return True
