import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('product_uom_qty')
    def _check_rounding(self):
        """Vérifie si la quantité est arrondie et ajoute un log."""
        precision = self.product_id.uom_precision or 3  # Par défaut, 3 décimales
        rounded_qty = round(self.product_uom_qty, precision)
        if self.product_uom_qty != rounded_qty:
            _logger.warning(
                "Quantité arrondie pour la ligne ID %s : de %s à %s (précision %s)",
                self.id, self.product_uom_qty, rounded_qty, precision
            )
            self.product_uom_qty = rounded_qty
