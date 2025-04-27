from odoo import models

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_displayed_quantity(self):
        """Retourne la quantité affichée avec 3 décimales."""
        precision = 3  # On force 3 décimales
        rounded_uom_qty = round(self.product_uom_qty, precision)
        return int(rounded_uom_qty) == rounded_uom_qty and int(rounded_uom_qty) or rounded_uom_qty
