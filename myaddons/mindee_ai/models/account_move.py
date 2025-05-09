# -*- coding: utf-8 -*-
from odoo import models, fields
from mindee import Client, product
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    pdf_attachment_id = fields.Many2one('ir.attachment', string="PDF OCR")  # CHAMP DÉFINI CORRECTEMENT
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

    def action_ocr_fetch(self):
        api_key = self.env['ir.config_parameter'].sudo().get_param('mindee_ai.mindee_api_key')
        if not api_key:
            _logger.error("La clé API Mindee n'est pas définie dans les paramètres de configuration.")
            return False

        try:
            mindee_client = Client(api_key=api_key)
        except Exception as e:
            _logger.error(f"Échec de l'initialisation du client Mindee: {e}")
            return False

        template = self.env['product.template'].browse(30)
        if not template.exists():
            _logger.warning("Le template produit Éco-part ID 30 est introuvable.")
            return False

        ecotax_product = template.product_variant_id
        if not ecotax_product:
            _logger.warning("Aucune variante trouvée pour le produit Éco-part.")
            return False

        for move in self:
            for message in move.message_ids:
                for attachment in message.attachment_ids:
                    if "pdf" in attachment.display_name.lower():
                        try:
                            input_doc = mindee_client.source_from_b64string(
                                attachment.datas.decode(), attachment.display_name
                            )
                            api_response = mindee_client.parse(product.InvoiceV4, input_doc)
                        except Exception as e:
                            _logger.error(f"Erreur lors de la lecture du document {attachment.display_name}: {e}")
                            continue

                        move.pdf_attachment_id = attachment  # ICI c’est OK

                        document = api_response.document
                        partner_name = (
                            document.inference.prediction.supplier_name.value
                            if document.inference.prediction.supplier_name else "Nom Inconnu"
                        )
                        partner_id = self.env['res.partner'].search([("name", "ilike", partner_name)], limit=1)

                        if not partner_id:
                            partner_id = self.env['res.partner'].create({
                                "name": partner_name,
                                "street": document.inference.prediction.supplier_address.value or "Adresse non fournie",
                            })

                        line_ids = []
                        total_calculated_net = 0.0
                        total_calculated_tax = 0.0

                        line_items = document.inference.prediction.line_items or []
                        for item in line_items:
                            description = item.description or "Description non fournie"
                            unit_price = item.unit_price or 0.0
                            quantity = item.quantity or 1
                            product_code = item.product_code or None

                            product_id = False

                            if product_code:
                                product_id = self.env['product.product'].search([('default_code', '=', product_code)], limit=1)
                            if not product_id:
                                product_id = self.env['product.product'].search([('name', 'ilike', description)], limit=1)
                            if not product_id:
                                product_id = self.env['product.product'].create({
                                    'name': description,
                                    'type': 'consu',
                                    'list_price': unit_price,
                                    'purchase_ok': True,
                                    'sale_ok': False,
                                    'default_code': product_code or f"NEW-{description[:10].upper()}",
                                })
                                _logger.info(f"Produit créé : {description} avec une référence {product_code or 'générée automatiquement'}")

                            line_net = unit_price * quantity
                            total_calculated_net += line_net

                            line_data = {
                                "name": description,
                                "product_id": product_id.id,
                                "price_unit": unit_price,
                                "quantity": quantity,
                                "tax_ids": [(6, 0, product_id.supplier_taxes_id.ids)],
                            }
                            line_ids.append((0, 0, line_data))

                            has_ecopart_tax = any(tax.amount_type == 'fixed' for tax in product_id.supplier_taxes_id)
                            if has_ecopart_tax:
                                unit_measure = (item.unit_measure or "").lower()
                                if unit_measure == 'kg':
                                    weight_kg = quantity
                                elif product_id.weight:
                                    weight_kg = product_id.weight * quantity
                                else:
                                    weight_kg = 0.0

                                if weight_kg > 0:
                                    ecotax_line = {
                                        "name": f"Éco-part pour {description}",
                                        "product_id": ecotax_product.id,
                                        "quantity": weight_kg,
                                        "price_unit": ecotax_product.standard_price,
                                        "tax_ids": [(6, 0, ecotax_product.supplier_taxes_id.ids)],
                                    }
                                    line_ids.append((0, 0, ecotax_line))

                        document_total_net = document.inference.prediction.total_net.value or 0.0
                        document_total_amount = document.inference.prediction.total_amount.value or 0.0
                        document_total_tax = document.inference.prediction.total_tax.value or 0.0
                        total_calculated_amount = total_calculated_net + total_calculated_tax

                        if abs(document_total_net - total_calculated_net) > 0.01 or \
                           abs(document_total_tax - total_calculated_tax) > 0.01 or \
                           abs(document_total_amount - total_calculated_amount) > 0.01:
                            _logger.warning(f"Les totaux ne correspondent pas pour la facture {move.name} :\n"
                                            f"Total Net (Document) : {document_total_net}, Total Net (Calculé) : {total_calculated_net}\n"
                                            f"Total Tax (Document) : {document_total_tax}, Total Tax (Calculé) : {total_calculated_tax}\n"
                                            f"Total Amount (Document) : {document_total_amount}, Total Amount (Calculé) : {total_calculated_amount}")

                        move.write({
                            "partner_id": partner_id.id,
                            "invoice_date": document.inference.prediction.date.value if document.inference.prediction.date else None,
                            "invoice_date_due": document.inference.prediction.due_date.value if document.inference.prediction.due_date else None,
                            "ref": document.inference.prediction.invoice_number or "Référence inconnue",
                            "invoice_line_ids": line_ids,
                        })

        return True
