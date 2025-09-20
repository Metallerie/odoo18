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

    doctr_response = fields.Text(
        string="Réponse OCR JSON (kie_predictor)",
        readonly=True,
        store=True
    )

    def _normalize_date(self, date_str):
        if not date_str:
            return None
        date_str = date_str.strip().replace("-", "/").replace(".", "/")
        for fmt in ("%d/%m/%Y", "%Y/%m/%d", "%d/%m/%y"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except Exception:
                continue
        return None

    def group_words_into_lines(self, predictions, y_thresh=0.01):
        lines = []
        for word in sorted(predictions, key=lambda x: (x['bbox'][0][1] + x['bbox'][1][1]) / 2):
            cy = (word['bbox'][0][1] + word['bbox'][1][1]) / 2
            placed = False
            for line in lines:
                ly = (line[0]['bbox'][0][1] + line[0]['bbox'][1][1]) / 2
                if abs(ly - cy) <= y_thresh:
                    line.append(word)
                    placed = True
                    break
            if not placed:
                lines.append([word])
        return lines

    def line_to_phrase(self, line):
        line = sorted(line, key=lambda x: x['bbox'][0][0])
        phrase = " ".join([word['value'] for word in line])
        return phrase

    def action_ocr_fetch(self):
        for move in self:
            # Lecture du PDF attaché
            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = pdf_attachments[0]
            file_path = "/tmp/ocr_temp_file.pdf"
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(attachment.datas))

            # Appel du script OCR dans venv Doctr
            doctr_venv_python = "/data/venv_doctr/bin/python3"
            doctr_script_path = "/data/venv_doctr/kie_predictor_runner.py"
            try:
                result = subprocess.run(
                    [doctr_venv_python, doctr_script_path, file_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=90,
                    check=True,
                    encoding="utf-8"
                )
                ocr_json = result.stdout
                ocr_data = json.loads(ocr_json)
            except Exception as e:
                _logger.error("Erreur OCR kie_predictor pour %s: %s", attachment.name, str(e))
                raise UserError(f"Erreur OCR avec kie_predictor : {e}\n{result.stderr if 'result' in locals() else ''}")

            # Construction des lignes et des phrases dans Odoo (pas dans le script OCR)
            predictions = ocr_data.get("words", [])
            lines = self.group_words_into_lines(predictions, y_thresh=0.01)
            phrases = [self.line_to_phrase(line) for line in lines]

            move.doctr_response = json.dumps({"phrases": phrases}, indent=2, ensure_ascii=False)

            self.env["ir.attachment"].create({
                "name": f"KIE_{attachment.name}.json",
                "res_model": "account.move",
                "res_id": move.id,
                "type": "binary",
                "mimetype": "application/json",
                "datas": base64.b64encode(json.dumps({"phrases": phrases}, indent=2).encode("utf-8")),
            })

            # Analyse des phrases pour extraire les infos de la facture
            invoice_date = None
            invoice_number = None
            amount_total = None
            supplier_name = None

            for phrase in phrases:
                if not invoice_date and ("date" in phrase.lower() or "facture" in phrase.lower()):
                    possible_dates = [p for p in phrase.split() if "/" in p or "-" in p or "." in p]
                    if possible_dates:
                        invoice_date = self._normalize_date(possible_dates[0])
                if not invoice_number and ("facture" in phrase.lower() or "n°" in phrase.lower()):
                    nums = [p for p in phrase.split() if p.isdigit()]
                    if nums:
                        invoice_number = nums[0]
                if not amount_total and ("total" in phrase.lower()):
                    nums = [p.replace(",", ".") for p in phrase.split() if p.replace(",", ".").replace(".", "").isdigit()]
                    if nums:
                        try:
                            amount_total = float(nums[-1])
                        except Exception:
                            pass
                if not supplier_name and ("sarl" in phrase.lower() or "sas" in phrase.lower() or "eurl" in phrase.lower()):
                    supplier_name = phrase

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
