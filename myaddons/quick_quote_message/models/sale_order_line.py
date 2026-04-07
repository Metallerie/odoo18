from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    quick_quote_in_stock = fields.Boolean(
        string="En stock",
        default=True,
    )
