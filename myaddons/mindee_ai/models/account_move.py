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
        store=True
    )

    def _normalize_date(self, date_str):
        """Convertit une chaîne en date (dd/mm/yyyy ou dd-mm-yyyy)."""
        if not date_str:
            return None
        date_str = date_str.strip().replace("-", "/").replace(".", "/")
        for fmt in ("%d/%m/%Y", "%Y/%m/%d", "%d/%m/%y"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except Exception:
                continue
        return None

    def action_ocr_fetch(self):
        for move in self:
            # 1️⃣ Récupérer le PDF attaché
            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = pdf_attachments[0]

            file_path = "/tmp/ocr_temp_file.pdf"
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(attachment.datas))

            # 2️⃣ Appel du script Tesseract runner
            venv_python = "/data/odoo/odoo18-venv/bin/python3"
            tesseract_script_path = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/scripts/tesseract_runner.py"

            try:
                result = subprocess.run(
                    [venv_python, tesseract_script_path, file_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=180,
                    check=True,
                    encoding="utf-8"
                )
                ocr_json = result.stdout
                ocr_data = json.loads(ocr_json)

            except subprocess.CalledProcessError as e:
                _logger.error("OCR failed for %s", attachment.name)
                raise UserError(
                    f"Erreur OCR avec Tesseract :\n\nSTDERR:\n{e.stderr}\n\nSTDOUT:\n{e.stdout}"
                )
            except json.JSONDecodeError:
                _logger.error("OCR n'a pas renvoyé de JSON valide pour %s", attachment.name)
                raise UserError(
                    f"OCR n'a pas renvoyé de JSON valide pour {attachment.name}.\n\n"
                    f"Sortie brute (500 premiers caractères) :\n{result.stdout[:500]}"
                )
            except Exception as e:
                _logger.error("Unexpected OCR error for %s: %s", attachment.name, str(e))
                raise UserError(f"Erreur OCR avec Tesseract : {e}")

            # 3️⃣ Sauvegarde du JSON brut
            move.mindee_local_response = json.dumps(ocr_data, indent=2, ensure_ascii=False)

            self.env["ir.attachment"].create({
                "name": f"OCR_{attachment.name}.json",
                "res_model": "account.move",
                "res_id": move.id,
                "type": "binary",
                "mimetype": "application/json",
                "datas": base64.b64encode(json.dumps(ocr_data, indent=2).encode("utf-8")),
            })

            # 4️⃣ Lire les champs extraits
            parsed = {}
            if ocr_data.get("pages"):
                parsed = ocr_data["pages"][0].get("parsed", {})

            invoice_date = self._normalize_date(parsed.get("invoice_date"))
            invoice_number = parsed.get("invoice_number")
            amount_total = parsed.get("amount_total")  # pas encore extrait → viendra plus tard
            supplier_name = parsed.get("supplier_name")

            # 5️⃣ Mise à jour de la facture
            vals = {}
            if invoice_date:
                vals["invoice_date"] = invoice_date
            if invoice_number:
                vals["ref"] = invoice_number
            if amount_total:
                vals["amount_total"] = amount_total

            if supplier_name:
                partner = self.env["res.partner"].search([("name", "ilike", supplier_name)], limit=1)
                if not partner:
                    partner = self.env["res.partner"].create({
                        "name": supplier_name,
                        "supplier_rank": 1,
                    })
                vals["partner_id"] = partner.id

            if vals:
                try:
                    move.write(vals)
                except Exception as e:
                    raise UserError(f"Erreur d’écriture dans la facture : {e}")

        return True
