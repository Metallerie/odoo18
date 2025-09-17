# PATCH COMPLET pour Mindee Local
# à coller/remplacer dans mindee_ai/models/account_move.py

import base64
import os
import tempfile
import logging
import requests
from odoo import models, fields

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    pdf_attachment_id = fields.Many2one('ir.attachment', string="PDF OCR")
    show_pdf_button = fields.Boolean(compute='_compute_show_pdf_button', store=True)

    def _compute_show_pdf_button(self):
        for move in self:
            move.show_pdf_button = bool(move.pdf_attachment_id)

    def action_open_pdf_viewer(self):
        self.ensure_one()
        if self.pdf_attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{self.pdf_attachment_id.id}?download=false',
                'target': 'new',
            }
        return False

    def _write_tmp_from_attachment(self, attachment):
        try:
            raw = base64.b64decode(attachment.datas or b"")
            suffix = ".pdf"
            fd, tmp_path = tempfile.mkstemp(prefix=f"mindee_{attachment.id}_", suffix=suffix)
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
            return tmp_path
        except Exception as e:
            _logger.error(f"Impossible d'écrire le fichier temporaire: {e}")
            return None

    def action_ocr_fetch(self):
        LOCAL_ENDPOINT = "http://127.0.0.1:1998/ocr"  # URL de Mindee local

        for move in self:
            for message in move.message_ids:
                for attachment in message.attachment_ids:
                    if "pdf" not in (attachment.display_name or "").lower():
                        continue

                    tmp_path = self._write_tmp_from_attachment(attachment)
                    if not tmp_path:
                        continue

                    try:
                        with open(tmp_path, 'rb') as f:
                            response = requests.post(LOCAL_ENDPOINT, files={'file': f})
                        os.remove(tmp_path)
                    except Exception as e:
                        _logger.error(f"Erreur requête OCR Mindee local: {e}")
                        continue

                    if response.status_code != 200:
                        _logger.warning(f"Mindee local a retourné une erreur: {response.status_code}")
                        continue

                    try:
                        result = response.json().get('data', {}).get('fields', {})
                    except Exception as e:
                        _logger.error(f"Erreur parsing JSON Mindee local: {e}")
                        continue

                    partner_name = result.get("supplier_name", "Nom Inconnu")
                    partner_addr = result.get("supplier_address")

                    partner = self.env['res.partner'].search([("name", "ilike", partner_name)], limit=1)
                    if not partner:
                        partner_vals = {"name": partner_name}
                        if partner_addr:
                            partner_vals["street"] = partner_addr
                        partner = self.env['res.partner'].create(partner_vals)

                    move.pdf_attachment_id = attachment

                    move.write({
                        "partner_id": partner.id,
                        "invoice_date": result.get("date"),
                        "invoice_date_due": result.get("due_date"),
                        "ref": result.get("invoice_number"),
                        "invoice_line_ids": [],  # pas encore géré car line_items est vide
                    })

        return True
