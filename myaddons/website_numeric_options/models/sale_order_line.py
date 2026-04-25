# -*- coding: utf-8 -*-

import math
import re

from odoo import api, models
from odoo.tools.float_utils import float_compare


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

    def _format_numeric_value(self, value):
        if value is None:
            return ""

        value = float(value)

        if value.is_integer():
            return str(int(value))

        return str(round(value, 4)).replace(".", ",")

    def _get_numeric_values(self):
        self.ensure_one()
        values_map = {}

        for custom_value in self.product_custom_attribute_value_ids:
            ptav = custom_value.custom_product_template_attribute_value_id
            if not ptav:
                continue

            pav = ptav.product_attribute_value_id
            if not pav:
                continue

            if pav.value_input_type == "numeric":
                number = self._parse_numeric_value(custom_value.custom_value)
                if number is not None:
                    values_map[pav.id] = number

        return values_map

    def _get_computed_order_qty_option(self):
        return self.env["product.attribute.value"].search([
            ("value_input_type", "=", "computed"),
            ("use_as_order_qty", "=", True),
        ], limit=1)

    def _get_numeric_computed_qty(self):
        self.ensure_one()

        values_map = self._get_numeric_values()
        if not values_map:
            return False, False, False

        computed = self._get_computed_order_qty_option()
        if not computed:
            return False, False, False

        if (
            computed.calc_operand_1_id.id in values_map
            and computed.calc_operand_2_id.id in values_map
        ):
            result = computed.compute_option_value(values_map)
            if result and result > 0:
                qty_to_set = math.ceil(result) if computed.round_order_qty_up else result
                return computed, result, qty_to_set

        return False, False, False

    def _find_computed_ptav(self, computed):
        self.ensure_one()

        if not self.product_template_id:
            return False

        ptavs = self.product_template_id.valid_product_template_attribute_line_ids.mapped(
            "product_template_value_ids"
        )

        return ptavs.filtered(
            lambda ptav: ptav.product_attribute_value_id == computed
        )[:1]

    def _set_computed_custom_value(self, computed, result):
        self.ensure_one()

        if not computed or not result or not self.id:
            return

        result_text = self._format_numeric_value(result)

        for custom_value in self.product_custom_attribute_value_ids:
            ptav = custom_value.custom_product_template_attribute_value_id
            if not ptav:
                continue

            pav = ptav.product_attribute_value_id
            if pav == computed:
                if custom_value.custom_value != result_text:
                    custom_value.with_context(skip_numeric_option_qty=True).write({
                        "custom_value": result_text,
                    })
                return

        computed_ptav = self._find_computed_ptav(computed)
        if not computed_ptav:
            return

        self.env["product.attribute.custom.value"].with_context(
            skip_numeric_option_qty=True
        ).create({
            "sale_order_line_id": self.id,
            "custom_product_template_attribute_value_id": computed_ptav.id,
            "custom_value": result_text,
        })

    def _apply_numeric_logic(self):
        if self.env.context.get("skip_numeric_option_qty"):
            return

        for line in self:
            computed, result, qty_to_set = line._get_numeric_computed_qty()
            if not computed or not result or not qty_to_set:
                continue

            # On écrit l'option calculée avec la valeur exacte.
            line._set_computed_custom_value(computed, result)

            # On met la quantité de commande avec ou sans arrondi.
            precision = line.product_uom.rounding if line.product_uom else 0.01

            if float_compare(line.product_uom_qty, qty_to_set, precision_rounding=precision) != 0:
                line.with_context(skip_numeric_option_qty=True).write({
                    "product_uom_qty": qty_to_set,
                })

    @api.onchange(
        "product_custom_attribute_value_ids",
        "product_custom_attribute_value_ids.custom_value",
    )
    def _onchange_numeric_options(self):
        for line in self:
            computed, result, qty_to_set = line._get_numeric_computed_qty()
            if not computed or not result or not qty_to_set:
                continue

            result_text = line._format_numeric_value(result)

            for custom_value in line.product_custom_attribute_value_ids:
                ptav = custom_value.custom_product_template_attribute_value_id
                if not ptav:
                    continue

                pav = ptav.product_attribute_value_id
                if pav == computed:
                    custom_value.custom_value = result_text

            line.product_uom_qty = qty_to_set

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._apply_numeric_logic()
        return lines

    def write(self, vals):
        res = super().write(vals)

        if not self.env.context.get("skip_numeric_option_qty"):
            self._apply_numeric_logic()

        return res
