import base64
import json
import logging
import subprocess
from datetime import datetime

from odoo import models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    mindee_local_response = fields.Text(
        string="Réponse OCR JSON (Tesseract OCR)",
        readonly=True,
        store=True
    )

    # ----------------------------
    # 🔧 Utilitaires
    # ----------------------------
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

    def _match_partner_from_ocr(self, ocr_data):
        """Trouve le fournisseur à partir des règles OCR ou du texte brut."""
        raw_text = " ".join([p.get("content", "") for p in ocr_data.get("pages", [])])

        Rule = self.env["ocr.configuration.rule.partner"]
        Partner = self.env["res.partner"]

        # 1. Vérifie les règles OCR configurées
        rules = Rule.search([("active", "=", True)])
        for rule in rules:
            if rule.keyword and rule.keyword.lower() in raw_text.lower():
                return rule.partner_id

        # 2. Fallback → recherche basique (nom dans OCR)
        common_names = ["Comptoir Commercial du Languedoc", "CCL"]
        for name in common_names:
            if name.lower() in raw_text.lower():
                partner = Partner.search([("name", "ilike", name)], limit=1)
                if partner:
                    return partner

        return False

    # ----------------------------
    # 🚀 Action OCR
    # ----------------------------
    def action_ocr_fetch(self):
        for move in self:
            # 1. Récupérer le PDF attaché
            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = pdf_attachments[0]

            file_path = "/tmp/ocr_temp_file.pdf"
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(attachment.datas))

            # 2. Appel du script Tesseract runner
            venv_python = "/data/odoo/metal-odoo18-p8179/odoo18-venv/bin/python3"
            tesseract_script_path = "/data/odoo/metal-odoo18-p8179/scripts/tesseract_runner.py"

            try:
                result = subprocess.run(
                    [venv_python, tesseract_script_path, file_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=180,
                    check=True,
                    encoding="utf-8"
                )
                ocr_json = result.stdout.strip()
                ocr_data = json.loads(ocr_json)

            except json.JSONDecodeError:
                raise UserError(
                    f"OCR n'a pas renvoyé de JSON valide pour {attachment.name}.\n\n"
                    f"Sortie brute (500 premiers caractères) :\n{result.stdout[:500]}"
                )
            except subprocess.CalledProcessError as e:
                _logger.error("OCR failed for %s", attachment.name)
                raise UserError(
                    f"Erreur OCR avec Tesseract :\n\nSTDERR:\n{e.stderr}\n\nSTDOUT:\n{e.stdout}"
                )
            except Exception as e:
                _logger.error("Unexpected OCR error for %s: %s", attachment.name, str(e))
                raise UserError(f"Erreur OCR avec Tesseract : {e}")

            # 3. Sauvegarder le JSON brut
            move.mindee_local_response = json.dumps(ocr_data, indent=2, ensure_ascii=False)

            self.env["ir.attachment"].create({
                "name": f"OCR_{attachment.name}.json",
                "res_model": "account.move",
                "res_id": move.id,
                "type": "binary",
                "mimetype": "application/json",
                "datas": base64.b64encode(json.dumps(ocr_data, indent=2).encode("utf-8")),
            })

            # 4. Exploiter les données extraites
            parsed = {}
            if ocr_data.get("pages"):
                parsed = ocr_data["pages"][0].get("parsed", {})

            invoice_date = self._normalize_date(parsed.get("invoice_date"))
            invoice_number = parsed.get("invoice_number")
            net_ht = parsed.get("totals", {}).get("net_ht")
            tva = parsed.get("totals", {}).get("tva")
            net_a_payer = parsed.get("totals", {}).get("net_a_payer")

            # 5. Associer le fournisseur via les règles OCR
            partner = self._match_partner_from_ocr(ocr_data)

            # 6. Mise à jour de la facture
            vals = {
                "invoice_date": invoice_date,
                "ref": invoice_number,
            }

            if net_a_payer:
                try:
                    vals["amount_total"] = float(net_a_payer)
                except Exception:
                    pass

            if partner:
                vals["partner_id"] = partner.id

            try:
                move.write(vals)
            except Exception as e:
                raise UserError(f"Erreur d’écriture dans la facture : {e}")

        return True
