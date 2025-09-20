import base64
import json
import logging
import subprocess
from datetime import datetime

from odoo import models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    mindee_local_response = fields.Text(
        string="Réponse OCR JSON (Doctr OCR)",
        readonly=True,
        store=True
    )

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

            # 2. Lancer le script OCR (ocr_predictor_runner.py) dans le venv Doctr
            doctr_venv_python = "/data/doctr-venv/bin/python3"
            doctr_script_path = "/data/doctr-venv/ocr_predictor_runner.py"

            try:
                result = subprocess.run(
                    [doctr_venv_python, doctr_script_path, file_path],
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
                    f"Erreur OCR avec Doctr :\n\nSTDERR:\n{e.stderr}\n\nSTDOUT:\n{e.stdout}"
                )
            except Exception as e:
                _logger.error("Unexpected OCR error for %s: %s", attachment.name, str(e))
                raise UserError(f"Erreur OCR avec Doctr : {e}")

            # 3. Sauvegarder le JSON brut dans le champ + pièce jointe
            move.mindee_local_response = json.dumps(ocr_data, indent=2, ensure_ascii=False)

            self.env["ir.attachment"].create({
                "name": f"OCR_{attachment.name}.json",
                "res_model": "account.move",
                "res_id": move.id,
                "type": "binary",
                "mimetype": "application/json",
                "datas": base64.b64encode(json.dumps(ocr_data, indent=2).encode("utf-8")),
            })

            # 4. Exploiter directement les phrases extraites par le runner OCR
            phrases = ocr_data.get("phrases", [])

            invoice_date = None
            invoice_number = None
            amount_total = None
            supplier_name = None

            for phrase in phrases:
                low = phrase.lower()

                if not invoice_date and ("date" in low or "facture" in low):
                    possible_dates = [p for p in phrase.split() if "/" in p or "-" in p or "." in p]
                    if possible_dates:
                        invoice_date = self._normalize_date(possible_dates[0])

                if not invoice_number and ("facture" in low or "n°" in low or "no" in low):
                    nums = [p for p in phrase.split() if p.isdigit()]
                    if nums:
                        invoice_number = nums[0]

                if not amount_total and "total" in low:
                    nums = [
                        p.replace(",", ".")
                        for p in phrase.split()
                        if p.replace(",", ".").replace(".", "").isdigit()
                    ]
                    if nums:
                        try:
                            amount_total = float(nums[-1])
                        except Exception:
                            pass

                if not supplier_name and any(soc in low for soc in ("sarl", "sas", "eurl", "sa", "sci", "scop")):
                    supplier_name = phrase

            # 5. Mise à jour de la facture avec les infos détectées
            vals = {
                "invoice_date": invoice_date,
                "ref": invoice_number,
                "amount_total": amount_total,
            }

            if supplier_name:
                partner = self.env["res.partner"].search([("name", "ilike", supplier_name)], limit=1)
                if not partner:
                    partner = self.env["res.partner"].create({
                        "name": supplier_name,
                        "supplier_rank": 1,
                    })
                vals["partner_id"] = partner.id

            try:
                move.write(vals)
            except Exception as e:
                raise UserError(f"Erreur d’écriture dans la facture : {e}")

        return True
