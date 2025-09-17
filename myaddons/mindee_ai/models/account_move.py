# -*- coding: utf-8 -*-
import base64
import os
import tempfile
import logging
from datetime import datetime
from odoo import models, fields

# --- Mindee v2 (MLA) ---# -*- coding: utf-8 -*-
import base64
import os
import tempfile
import logging
from datetime import datetime
from odoo import models, fields
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
            suffix = ".pdf" if attachment.mimetype == 'application/pdf' else ".bin"
            fd, tmp_path = tempfile.mkstemp(suffix=suffix)
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
            return tmp_path
        except Exception as e:
            _logger.error(f"Erreur lors de la création du fichier temporaire : {e}")
            return None

    def _convert_date(self, value):
        try:
            return datetime.strptime(value, '%d/%m/%Y').date()
        except Exception as e:
            _logger.warning(f"Date invalide '{value}' : {e}")
            return False

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
                        files = {'file': open(tmp_path, 'rb')}
                        response = requests.post("http://127.0.0.1:1998/ocr", files=files)
                        if response.status_code != 200:
                            _logger.error(f"Mindee local OCR failed: {response.text}")
                            continue
                        data = response.json().get("data", {})

                        # Log complet JSON
                        _logger.info("[MINDEE JSON] %s", data)

                        partner_name = data.get("supplier_name") or "Nom Inconnu"
                        partner_addr = data.get("supplier_address")
                        partner = self.env['res.partner'].search([("name", "ilike", partner_name)], limit=1)
                        if not partner:
                            partner_vals = {"name": partner_name, "street": partner_addr or False}
                            partner = self.env['res.partner'].create(partner_vals)

                        move.write({
                            "partner_id": partner.id,
                            "invoice_date": self._convert_date(data.get("date")),
                            "invoice_date_due": self._convert_date(data.get("due_date")),
                            "ref": data.get("invoice_number"),
                            "pdf_attachment_id": attachment.id,
                        })
                    except Exception as e:
                        _logger.error(f"Erreur OCR: {e}")
                    finally:
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass

        return True

from mindee import ClientV2, InferenceParameters, PathInput

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

    @staticmethod
    def _m_field(fields_dict, key, default=None):
        fld = fields_dict.get(key)
        return getattr(fld, "value", default) if fld is not None else default

    @staticmethod
    def _m_items(fields_dict, key):
        fld = fields_dict.get(key)
        return getattr(fld, "items", []) if fld is not None else []

    def _parse_date_fr_to_iso(self, date_str):
        try:
            return datetime.strptime(date_str, "%d/%m/%Y").date()
        except Exception:
            return None

    def _write_tmp_from_attachment(self, attachment):
        try:
            raw = base64.b64decode(attachment.datas or b"")
            suffix = ".pdf" if attachment.display_name.lower().endswith(".pdf") else ".pdf"
            fd, tmp_path = tempfile.mkstemp(prefix=f"mindee_{attachment.id}_", suffix=suffix)
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
            return tmp_path
        except Exception as e:
            _logger.error(f"Impossible d'écrire le fichier temporaire pour {attachment.display_name}: {e}")
            return None

    def action_ocr_fetch(self):
        ICP = self.env['ir.config_parameter'].sudo()
        api_key = ICP.get_param('mindee_ai.mindee_api_key')
        model_id = ICP.get_param('mindee_ai.model_id')
        if not api_key or not model_id:
            _logger.error("Clé API Mindee ou Model ID manquant.")
            return False

        try:
            mindee_client = ClientV2(api_key)
        except Exception as e:
            _logger.error(f"Init Mindee ClientV2 KO: {e}")
            return False

        params = InferenceParameters(model_id=model_id)
        template = self.env['product.template'].browse(30)
        ecotax_product = template.product_variant_id if template.exists() else False

        for move in self:
            for message in move.message_ids:
                for attachment in message.attachment_ids:
                    if "pdf" not in (attachment.display_name or "").lower():
                        continue

                    tmp_path = self._write_tmp_from_attachment(attachment)
                    if not tmp_path:
                        continue

                    try:
                        input_src = PathInput(tmp_path)
                        resp = mindee_client.enqueue_and_get_inference(input_src, params)
                    except Exception as e:
                        _logger.error(f"Mindee v2 erreur pour {attachment.display_name}: {e}")
                        continue
                    finally:
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass

                    move.pdf_attachment_id = attachment
                    fields_dict = getattr(getattr(resp, "inference", None), "result", None)
                    fields_dict = getattr(fields_dict, "fields", {}) if fields_dict else {}

                    partner_name = self._m_field(fields_dict, "supplier_name", "Nom Inconnu")
                    partner_addr = self._m_field(fields_dict, "supplier_address")

                    partner = self.env['res.partner'].search([("name", "ilike", partner_name)], limit=1)
                    if not partner:
                        partner_vals = {"name": partner_name}
                        if partner_addr:
                            partner_vals["street"] = partner_addr
                        partner = self.env['res.partner'].create(partner_vals)

                    line_ids = []
                    for obj in self._m_items(fields_dict, "line_items"):
                        sub = getattr(obj, "fields", {})
                        description = getattr(sub.get("description"), "value", "Sans description")
                        unit_price = float(getattr(sub.get("unit_price"), "value", 0.0))
                        quantity = float(getattr(sub.get("quantity"), "value", 1.0))
                        product_code = getattr(sub.get("product_code"), "value", None)
                        unit_measure = (getattr(sub.get("unit_measure"), "value", "") or "").lower()

                        product_id = self.env['product.product'].search(
                            [('default_code', '=', product_code)], limit=1) if product_code else False
                        if not product_id:
                            product_id = self.env['product.product'].search(
                                [('name', 'ilike', description)], limit=1)
                        if not product_id:
                            product_id = self.env['product.product'].create({
                                'name': description,
                                'type': 'consu',
                                'list_price': unit_price,
                                'purchase_ok': True,
                                'sale_ok': False,
                                'default_code': product_code or description[:10].upper(),
                            })

                        line_data = {
                            "name": description,
                            "product_id": product_id.id,
                            "price_unit": unit_price,
                            "quantity": quantity,
                            "tax_ids": [(6, 0, product_id.supplier_taxes_id.ids)],
                        }
                        line_ids.append((0, 0, line_data))

                    move.write({
                        "partner_id": partner.id,
                        "invoice_date": self._parse_date_fr_to_iso(self._m_field(fields_dict, "date")),
                        "invoice_date_due": self._parse_date_fr_to_iso(self._m_field(fields_dict, "due_date")),
                        "ref": self._m_field(fields_dict, "invoice_number", "Réf inconnue"),
                        "invoice_line_ids": line_ids,
                    })

        return True
