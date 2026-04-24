# -*- coding: utf-8 -*-
#product_template_attribute_value.py

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    value_input_type = fields.Selection(
        [
            ("text", "Texte"),
            ("numeric", "Numérique"),
            ("computed", "Calculé"),
        ],
        string="Type de saisie",
        default="text",
    )
    use_as_order_qty = fields.Boolean(
        string="Utiliser comme quantité de commande",
        default=False,
    )
    numeric_type = fields.Selection(
        [
            ("int", "Entier"),
            ("float", "Décimal"),
        ],
        string="Type numérique",
        default="float",
    )

    calc_operation = fields.Selection(
        [
            ("multiply", "Multiplication"),
        ],
        string="Opération",
    )

    calc_operand_1_id = fields.Many2one(
        "product.attribute.value",
        string="Opérande 1",
        domain="[('value_input_type', '=', 'numeric'), ('id', '!=', id)]",
    )

    calc_operand_2_id = fields.Many2one(
        "product.attribute.value",
        string="Opérande 2",
        domain="[('value_input_type', '=', 'numeric'), ('id', '!=', id), ('id', '!=', calc_operand_1_id)]",
    )

    is_computed_readonly = fields.Boolean(
        string="Résultat en lecture seule",
        default=True,
    )

    @api.constrains(
        "value_input_type",
        "calc_operation",
        "calc_operand_1_id",
        "calc_operand_2_id",
    )
    def _check_computed_configuration(self):
        for rec in self:
            if rec.value_input_type != "computed":
                continue

            if not rec.calc_operation:
                raise ValidationError("Une option calculée doit avoir une opération.")

            if not rec.calc_operand_1_id or not rec.calc_operand_2_id:
                raise ValidationError("Une option calculée doit avoir deux opérandes.")

            if rec.calc_operand_1_id == rec or rec.calc_operand_2_id == rec:
                raise ValidationError("Une option calculée ne peut pas se référencer elle-même.")

            if rec.calc_operand_1_id == rec.calc_operand_2_id:
                raise ValidationError("Les deux opérandes doivent être différentes.")

            if rec.calc_operand_1_id.value_input_type != "numeric":
                raise ValidationError("L'opérande 1 doit être une valeur numérique.")

            if rec.calc_operand_2_id.value_input_type != "numeric":
                raise ValidationError("L'opérande 2 doit être une valeur numérique.")

    @api.onchange("value_input_type")
    def _onchange_value_input_type(self):
        for rec in self:
            if rec.value_input_type != "computed":
                rec.calc_operation = False
                rec.calc_operand_1_id = False
                rec.calc_operand_2_id = False

            if rec.value_input_type != "numeric":
                rec.numeric_type = "float"

    def compute_option_value(self, values_map):
        self.ensure_one()

        if self.value_input_type != "computed":
            return values_map.get(self.id)

        left = values_map.get(self.calc_operand_1_id.id, 0.0)
        right = values_map.get(self.calc_operand_2_id.id, 0.0)

        try:
            left = float(str(left or "0").replace(",", "."))
            right = float(str(right or "0").replace(",", "."))
        except (TypeError, ValueError):
            return 0.0

        if self.calc_operation == "multiply":
            return left * right

        return 0.0
