# ocaaddons/website_sale_secondary_unit/models/sale_order.py
from odoo import api, models
from odoo.http import request
from odoo.tools.float_utils import float_round


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _cart_find_product_line(self, product_id=None, line_id=None, **kwargs):
        so_lines = super()._cart_find_product_line(
            product_id=product_id, line_id=line_id, **kwargs
        )
        if so_lines:
            if line_id:
                sol = self.env["sale.order.line"].browse(line_id)
                secondary_uom_id = sol.secondary_uom_id.id
            else:
                secondary_uom_id = self.env.context.get("secondary_uom_id", False)
            so_lines = so_lines.filtered(lambda x: x.secondary_uom_id.id == secondary_uom_id)
        return so_lines

    def _prepare_order_line_values(
        self,
        product_id,
        quantity,
        linked_line_id=False,
        no_variant_attribute_values=None,
        product_custom_attribute_values=None,
        **kwargs,
    ):
        values = super()._prepare_order_line_values(
            product_id,
            quantity,
            linked_line_id=linked_line_id,
            no_variant_attribute_values=no_variant_attribute_values,
            product_custom_attribute_values=product_custom_attribute_values,
            **kwargs,
        )
        values["secondary_uom_id"] = self.env.context.get("secondary_uom_id")
        # ✅ si le website a fourni une qty secondaire, on la stocke telle quelle
        if self.env.context.get("secondary_uom_qty") is not None:
            values["secondary_uom_qty"] = self.env.context["secondary_uom_qty"]
        return values

    def _prepare_order_line_update_values(self, order_line, quantity, linked_line_id=False, **kwargs):
        values = super()._prepare_order_line_update_values(
            order_line, quantity, linked_line_id=linked_line_id, **kwargs
        )
        secondary_uom_id = self.env.context.get("secondary_uom_id")
        if secondary_uom_id != order_line.secondary_uom_id.id:
            values["secondary_uom_id"] = secondary_uom_id
        if self.env.context.get("secondary_uom_qty") is not None:
            values["secondary_uom_qty"] = self.env.context["secondary_uom_qty"]
        return values

    # ⚠️ IMPORTANT : on ne fait plus la conversion ici avec allow_uom_sell,
    # car désormais c'est le controller website qui convertit proprement.
    # On garde juste le passage du secondary_uom_id via context (déjà géré).
