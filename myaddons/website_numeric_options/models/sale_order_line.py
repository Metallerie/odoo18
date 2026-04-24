# -*- coding: utf-8 -*-

import re
from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _parse_numeric_value(self, value):
        if not value:
            return None

        value = str(value).replace(",", ".")
        match = re.search(r"[-+]?\d*\.?\d+", value)

        if not match:
            return None

        try:
            return float(match.group(0))
        except ValueError:
            return None

    def _apply_numeric_logic(self):
        for line in self:

            if not line.product_custom_attribute_value_ids:
                continue

            values_map = {}

            for custom_value in line.product_custom_attribute_value_ids:

                ptav = custom_value.custom_product_template_attribute_value_id
                pav = ptav.product_attribute_value_id

                if pav.value_input_type == "numeric":
                    number = self._parse_numeric_value(custom_value.custom_value)

                    if number is not None:
                        values_map[pav.id] = number

            computed_values = self.env["product.attribute.value"].search([
                ("value_input_type", "=", "computed"),
                ("use_as_order_qty", "=", True),
            ])

            for computed in computed_values:

                if (
                    computed.calc_operand_1_id.id in values_map
                    and computed.calc_operand_2_id.id in values_map
                ):

                    result = computed.compute_option_value(values_map)

                    if result and result > 0:
                        line.product_uom_qty = result

    @api.depends(
        "product_custom_attribute_value_ids",
        "product_custom_attribute_value_ids.custom_value",
    )
    def _compute_amount(self):
        super()._compute_amount()
        self._apply_numeric_logic()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._apply_numeric_logic()
        return lines

    def write(self, vals):
        res = super().write(vals)
        self._apply_numeric_logic()
        return res
