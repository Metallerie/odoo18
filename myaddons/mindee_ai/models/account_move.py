# ✅ Nouveau script complet : mindee_ai/models/account_move.py
# Fonctionne avec Mindee local (http://127.0.0.1:1998/ocr)
# - Crée une pièce jointe JSON
# - Met à jour le fournisseur, la date et le numéro de facture

import base64
import json
import logging
import requests

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    mindee_local_response = fields.Text(string="Réponse OCR JSON (Mindee)", readonly=True, store=True)

    def action_ocr_fetch(self):
        for move in self:
            if not move.attachment_ids:
                raise UserError("Aucune pièce jointe trouvée sur cette facture.")

            # ⚠️ Ici on devrait filtrer les PDF, sinon tu risques d’envoyer le JSON
            attachment = move.attachment_ids.filtered(lambda a: a.mimetype == 'application/pdf')[:1]
            if not attachment:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = attachment[0]

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

            vals = {
                'invoice_date': safe_date(fields_map.get("date")),
                'invoice_date_due': safe_date(fields_map.get("due_date")),
                'invoice_origin': fields_map.get("invoice_number"),
                'amount_untaxed': fields_map.get("total_net"),
                'amount_tax': fields_map.get("total_tax"),
                'amount_total': fields_map.get("total_amount"),
            }

            # ✅ Détection du fournisseur par son nom
            supplier_name = fields_map.get("supplier_name")
            if supplier_name:
                partner = self.env['res.partner'].search([('name', 'ilike', supplier_name)], limit=1)
                if partner:
                    vals['partner_id'] = partner.id
                else:
                    # Si le fournisseur n’existe pas → on le crée automatiquement
                    partner = self.env['res.partner'].create({
                        'name': supplier_name,
                        'supplier_rank': 1,
                    })
                    vals['partner_id'] = partner.id
                _logger.info("Fournisseur détecté/assigné : %s (id=%s)", supplier_name, vals['partner_id'])

            try:
                move.write(vals)
                _logger.info("Facture %s mise à jour avec les données OCR Mindee local", move.name)
            except Exception as e:
                _logger.error("Erreur d’écriture dans la facture %s : %s", move.name, str(e))
                raise UserError(f"Erreur d’écriture dans la facture : {e}")

        return True
