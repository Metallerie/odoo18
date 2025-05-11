from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_update_stock_from_invoice(self):
        for move in self:
            if move.move_type != 'in_invoice' or move.state != 'posted':
                continue

            for line in move.invoice_line_ids:
                product = line.product_id
                if not product or product.type != 'product':
                    continue

                qty_po = line.quantity
                uom_po = product.uom_po_id
                uom_stock = product.uom_id

                try:
                    if uom_po.category_id == uom_stock.category_id:
                        qty_stock = uom_po._compute_quantity(qty_po, uom_stock)
                    else:
                        uom_ref = product.uom_id.name.upper()
                        if uom_ref in ('KG', 'KILOGRAMME'):
                            qty_stock = qty_po * product.product_kg_ml
                        elif uom_ref in ('ML', 'MÈTRE', 'M'):
                            if product.product_kg_ml > 0:
                                qty_stock = qty_po / product.product_kg_ml
                            else:
                                _logger.warning(f"⚠️ {product.display_name} : product_kg_ml manquant.")
                                continue
                        else:
                            _logger.warning(f"⚠️ Conversion inconnue pour {product.display_name} (UoM: {uom_ref})")
                            continue

                    location = move.company_id.partner_id.property_stock_supplier
                    self.env['stock.quant']._update_available_quantity(product, location, qty_stock)
                    _logger.info(f"✅ {product.display_name} ➝ +{qty_stock:.3f} {uom_stock.name}")

                except Exception as e:
                    _logger.error(f"❌ Erreur sur {product.display_name} : {str(e)}")

            move.message_post(body="📦 Mise à jour du stock effectuée à partir de la facture validée.")
        return True
