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
        string="Réponse OCR JSON (Doctr KIE)",
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
            # 1. Prendre le PDF attaché
            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = pdf_attachments[0]

            file_path = "/tmp/ocr_temp_file.pdf"
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(attachment.datas))

            # 2. Appel du script OCR dans le venv doctr
            doctr_venv_python = "/data/doctr-venv/bin/python3"
            doctr_script_path = "/data/doctr-venv/kie_predictor_runner.py"

            try:
                result = subprocess.run(
                    [doctr_venv_python, doctr_script_path, file_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=120,
                    check=True,
                    encoding="utf-8"
                )
                ocr_json = result.stdout
                ocr_data = json.loads(ocr_json)

            except subprocess.CalledProcessError as e:
                _logger.error("OCR failed for %s", attachment.name)
                _logger.error("stdout: %s", e.stdout)
                _logger.error("stderr: %s", e.stderr)
                raise UserError(
                    f"Erreur OCR avec kie_predictor :\n\nSTDERR:\n{e.stderr}\n\nSTDOUT:\n{e.stdout}"
                )
            except Exception as e:
                _logger.error("Unexpected OCR error for %s: %s", attachment.name, str(e))
                raise UserError(f"Erreur OCR avec kie_predictor : {e}")

            # 3. Sauvegarde du JSON brut
            move.mindee_local_response = json.dumps(ocr_data, indent=2, ensure_ascii=False)

            self.env["ir.attachment"].create({
                "name": f"KIE_{attachment.name}.json",
                "res_model": "account.move",
                "res_id": move.id,
                "type": "binary",
                "mimetype": "application/json",
                "datas": base64.b64encode(json.dumps(ocr_data, indent=2).encode("utf-8")),
            })

            # 4. Reconstruction des phrases depuis les mots bruts
            phrases = []
            current_page = 1
            line = []

            for w in ocr_data:
                if w.get("page") != current_page:
                    if line:
                        phrases.append(" ".join(line))
                        line = []
                    current_page = w.get("page")
                line.append(w.get("value", ""))

            if line:
                phrases.append(" ".join(line))

            # 5. Extraction heuristique basique
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

            # 6. Mise à jour de la facture
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
