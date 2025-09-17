# -*- coding: utf-8 -*-
import base64
import os
import tempfile
import logging
import json
from datetime import datetime
from odoo import models, fields
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DATE_FORMAT
import requests

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
            name = (attachment.display_name or "document.pdf").lower()
            if name.endswith(".jpg") or name.endswith(".jpeg"):
                suffix = ".jpg"
            elif name.endswith(".png"):
                suffix = ".png"
            fd, tmp_path = tempfile.mkstemp(prefix=f"mindee_{attachment.id}_", suffix=suffix)
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
            return tmp_path
        except Exception as e:
            _logger.error(f"Erreur lors de l'écriture du fichier temporaire: {e}")
            return None

    def action_ocr_fetch(self):
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
                            response = requests.post(
                                "http://127.0.0.1:1998/ocr",
                                files={"file": f},
                                timeout=30
                            )
                        os.remove(tmp_path)
                        if response.status_code != 200:
                            _logger.error(f"Mindee v2 erreur pour {attachment.display_name}: {response.text}")
                            continue

                        result_json = response.json()
                        fields_dict = result_json.get("data", {}).get("fields", {})

                        # Log dans fichier JSON pour debug
                        try:
                            log_path = f"/tmp/mindee_debug_{attachment.id}.json"
                            with open(log_path, "w") as f:
                                json.dump(fields_dict, f, indent=2, ensure_ascii=False)
                            _logger.info(f"📄 Résultat OCR sauvegardé dans {log_path}")
                        except Exception as e:
                            _logger.warning(f"Échec d'enregistrement debug JSON: {e}")

                        # Lien vers pièce jointe
                        move.pdf_attachment_id = attachment

                        partner_name = fields_dict.get("supplier_name") or "Nom Inconnu"
                        partner = self.env['res.partner'].search([("name", "ilike", partner_name)], limit=1)
                        if not partner:
                            partner = self.env['res.partner'].create({"name": partner_name})

                        # Correction date au format Odoo
                        def parse_date(date_str):
                            try:
                                return datetime.strptime(date_str, "%d/%m/%Y").strftime(DATE_FORMAT)
                            except Exception as e:
                                _logger.warning(f"Date invalide: {date_str} - {e}")
                                return False

                        vals = {
                            "partner_id": partner.id,
                            "invoice_date": parse_date(fields_dict.get("date")),
                            "invoice_date_due": parse_date(fields_dict.get("due_date")),
                            "ref": fields_dict.get("invoice_number") or "Référence inconnue",
                        }

                        _logger.info(f"🧾 Mise à jour de {move.name} avec {vals}")
                        move.write(vals)

                    except Exception as e:
                        _logger.error(f"Erreur lors du traitement Mindee v2: {e}")

        return True
