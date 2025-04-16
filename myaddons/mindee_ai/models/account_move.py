# -*- coding: utf-8 -*-
from odoo import models
from mindee import Client, product
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_ocr_fetch(self):
        api_key = self.env['ir.config_parameter'].sudo().get_param('mindee_api_key')
        if not api_key:
            _logger.error("La clé API Mindee n'est pas définie dans les paramètres de configuration.")
            return False

        try:
            mindee_client = Client(api_key=api_key)
        except Exception as e:
            _logger.error(f"Échec de l'initialisation du client Mindee: {e}")
            return False

        default_tax = self.env['account.tax'].search([('amount', '=', 20), ('type_tax_use', '=', 'purchase')], limit=1)
        if not default_tax:
            _logger.error("La taxe d'achat par défaut à 20% est introuvable.")
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

                        line_items = document.inference.prediction.line_items or []
                        line_ids = []
                        total_calculated_net = 0.0
                        total_calculated_tax = 0.0

                        for item in line_items:
                            description = item.description or "Description non fournie"
                            unit_price = item.unit_price or 0.0
                            quantity = item.quantity or 1
                            tax_rate = item.tax_rate or 0.0

                            product_id = self.env['product.product'].search([('name', 'ilike', description)], limit=1)
                            if not product_id:
                                product_id = self.env['product.product'].create({
                                    'name': description,
                                    'type': 'product',
                                    'list_price': unit_price,
                                    'purchase_ok': True,
                                    'sale_ok': False,
                                })
                                _logger.info(f"Produit créé : {description} avec un prix unitaire de {unit_price}")

                            line_net = unit_price * quantity
                            line_tax = line_net * (tax_rate / 100.0)
                            total_calculated_net += line_net
                            total_calculated_tax += line_tax

                            tax_ids = [(6, 0, [default_tax.id])] if tax_rate == 0.0 else [(6, 0, [tax_rate])]

                            line_data = {
                                "name": description,
                                "product_id": product_id.id,
                                "price_unit": unit_price,
                                "quantity": quantity,
                                "tax_ids": tax_ids,
                            }
                            line_ids.append((0, 0, line_data))

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
