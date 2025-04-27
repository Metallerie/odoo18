from odoo import models, fields

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_displayed_quantity(self):
        """Retourne la quantité affichée avec la précision définie sur le produit."""
        precision = self.product_id.uom_precision or 3  # Par défaut, 3 décimales
        return round(self.product_uom_qty, precision)
