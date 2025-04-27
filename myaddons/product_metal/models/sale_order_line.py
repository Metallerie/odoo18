from odoo import models

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_displayed_quantity(self):
        """Retourne la quantité affichée avec 3 décimales, ou 0.0 par défaut."""
        if self.product_uom_qty is None:
            return 0.0  # Retourne 0.0 si la quantité est None
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        rounded_uom_qty = round(self.product_uom_qty, precision)
        return int(rounded_uom_qty) == rounded_uom_qty and int(rounded_uom_qty) or rounded_uom_qty
