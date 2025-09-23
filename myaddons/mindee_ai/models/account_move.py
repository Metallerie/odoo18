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
        string="Réponse OCR JSON (Tesseract)",
        readonly=True,
        store=True,
    )

    def _normalize_date(self, date_str):
        """Convertit une chaîne en date si possible."""
        if not date_str:
            return None
        date_str = date_str.strip().replace("-", "/").replace(".", "/")
        for fmt in ("%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except Exception:
                continue
        return None

    def action_ocr_fetch(self):
        for move in self:
            # 1️⃣ Récupérer le PDF attaché
            pdf_attachments = move.attachment_ids.filtered(
                lambda a: a.mimetype == "application/pdf"
            )[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = pdf_attachments[0]

            file_path = "/tmp/ocr_temp_file.pdf"
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(attachment.datas))

            # 2️⃣ Lancer le script OCR
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
                ocr_data = json.loads(ocr_json)

            except subprocess.CalledProcessError as e:
                _logger.error("OCR failed for %s", attachment.name)
                raise UserError(
                    f"Erreur OCR avec Tesseract :\n\nSTDERR:\n{e.stderr}\n\nSTDOUT:\n{e.stdout}"
                )
            except Exception as e:
                _logger.error("Unexpected OCR error for %s: %s", attachment.name, str(e))
                raise UserError(f"Erreur OCR avec Tesseract : {e}")

            # 3️⃣ Sauvegarde du JSON brut
            move.mindee_local_response = json.dumps(
                ocr_data, indent=2, ensure_ascii=False
            )

            self.env["ir.attachment"].create(
                {
                    "name": f"OCR_{attachment.name}.json",
                    "res_model": "account.move",
                    "res_id": move.id,
                    "type": "binary",
                    "mimetype": "application/json",
                    "datas": base64.b64encode(
                        json.dumps(ocr_data, indent=2).encode("utf-8")
                    ),
                }
            )

            # 4️⃣ Lecture des données extraites
            parsed = {}
            if ocr_data.get("pages"):
                parsed = ocr_data["pages"][0].get("parsed", {})

            vals = {}
            if parsed.get("invoice_date"):
                vals["invoice_date"] = self._normalize_date(parsed["invoice_date"])
            if parsed.get("invoice_number"):
                vals["ref"] = parsed["invoice_number"]

            # 5️⃣ Application des règles OCR (ocr.configuration.rule)
            rules = self.env["ocr.configuration.rule"].search(
                [("active", "=", True)], order="sequence"
            )

            raw_text = " ".join(
                sum([p.get("phrases", []) for p in ocr_data.get("pages", [])], [])
            )
            invoice_number = parsed.get("invoice_number", "")
            partner_name_ocr = parsed.get("supplier_name", "")

            for rule in rules:
                value = None
                if rule.variable == "partner_name":
                    value = partner_name_ocr or raw_text
                elif rule.variable == "invoice_number":
                    value = invoice_number
                elif rule.variable == "invoice_date":
                    value = parsed.get("invoice_date", "")

                if not value:
                    continue

                matched = False
                if rule.condition_type == "text" and rule.value_text:
                    val = value.lower()
                    cmp = rule.value_text.lower()
                    if rule.operator == "contains" and cmp in val:
                        matched = True
                    elif rule.operator == "==" and val == cmp:
                        matched = True
                    elif rule.operator == "startswith" and val.startswith(cmp):
                        matched = True
                    elif rule.operator == "endswith" and val.endswith(cmp):
                        matched = True

                if matched:
                    if rule.partner_id:
                        vals["partner_id"] = rule.partner_id.id
                        _logger.info(
                            "OCR Rule matched: %s → Partner %s",
                            rule.name,
                            rule.partner_id.name,
                        )
                        break  # stop at first match

            # 6️⃣ Mise à jour de la facture
            if vals:
                try:
                    move.write(vals)
                except Exception as e:
                    raise UserError(f"Erreur d’écriture dans la facture : {e}")

        return True
