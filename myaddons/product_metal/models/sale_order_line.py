from odoo import models

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_displayed_quantity(self):
        """Retourne la quantité affichée avec la précision définie sur la variante product.product."""
        # Par défaut, on utilise une précision globale (par exemple, 3)
        default_precision = 3

        # Si la variante de produit a une précision personnalisée, utilisez-la
        precision = self.product_id.uom_precision or default_precision

        if self.product_uom_qty is None:
            return 0.0  # Retourne 0.0 si la quantité est vide

        rounded_uom_qty = round(self.product_uom_qty, precision)
        return rounded_uom_qty
