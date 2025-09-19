# ✅ Nouveau script complet : mindee_ai/models/account_move.py
# Fonctionne avec Mindee local (http://127.0.0.1:1998/ocr) et attache la réponse JSON brut en pièce jointe

import base64
import json
import logging
import requests
from odoo import models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    mindee_local_response = fields.Text(string="Réponse OCR (Mindee)", readonly=True)

    def action_ocr_fetch(self):
        for move in self:
            if not move.attachment_ids:
                raise UserError("Aucune pièce jointe trouvée sur cette facture.")

            attachment = move.attachment_ids[0]
            file_path = "/tmp/ocr_temp_file.pdf"
            with open(file_path, 'wb') as f:
                f.write(base64.b64decode(attachment.datas))

            try:
                response = requests.post(
                    "http://127.0.0.1:1998/ocr",
                    files={"file": open(file_path, "rb")},
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
            except Exception as e:
                _logger.error("Mindee v2 erreur pour %s: %s", attachment.name, str(e))
                raise UserError(f"Erreur OCR : {e}")

            _logger.info("Mindee v2 réponse pour %s : %s", attachment.name, result)

            # Écriture dans le champ + log
            move.mindee_local_response = json.dumps(result, indent=2, ensure_ascii=False)

            # Pièce jointe JSON
            self.env['ir.attachment'].create({
                'name': f"OCR_{attachment.name}.json",
                'res_model': 'account.move',
                'res_id': move.id,
                'type': 'binary',
                'mimetype': 'application/json',
                'datas': base64.b64encode(json.dumps(result, indent=2).encode('utf-8')),
            })

            # Formatage sécurisé pour les champs de la facture
            fields_map = result.get("data", {}).get("fields", {})

            def safe_date(date_str):
                try:
                    return fields.Date.to_date(date_str)
                except Exception:
                    return None

            move.write({
                'invoice_date': safe_date(fields_map.get("date")),
                'invoice_date_due': safe_date(fields_map.get("due_date")),
                'invoice_origin': fields_map.get("invoice_number"),
                'amount_untaxed': fields_map.get("total_net"),
                'amount_tax': fields_map.get("total_tax"),
                'amount_total': fields_map.get("total_amount"),
                # On ne touche pas aux lignes pour l'instant
            })

            _logger.info("Facture %s mise à jour avec les données OCR Mindee local", move.name)

        return True
