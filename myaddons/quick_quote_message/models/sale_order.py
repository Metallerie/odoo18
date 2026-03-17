from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_open_quick_quote(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Devis rapide",
            "res_model": "quick.quote.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_sale_order_id": self.id,
            },
        }
