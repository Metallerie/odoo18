# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplateAttributeValue(models.Model):
    _inherit = "product.template.attribute.value"

    value_input_type = fields.Selection(
        selection=[
            ("text", "Texte"),
            ("numeric", "Numérique"),
            ("computed", "Calculé"),
        ],
        string="Type de saisie",
        default="text",
    )

    numeric_type = fields.Selection(
        selection=[
            ("int", "Entier"),
            ("float", "Décimal"),
        ],
        string="Type numérique",
        default="float",
    )

    calc_operation = fields.Selection(
        selection=[
            ("multiply", "Multiplication"),
        ],
        string="Opération de calcul",
    )

    calc_operand_1_id = fields.Many2one(
        "product.template.attribute.value",
        string="Opérande 1",
        domain="[('id', '!=', id)]",
    )

    calc_operand_2_id = fields.Many2one(
        "product.template.attribute.value",
        string="Opérande 2",
        domain="[('id', '!=', id), ('id', '!=', calc_operand_1_id)]",
    )

    is_computed_readonly = fields.Boolean(
        string="Résultat en lecture seule",
        default=True,
    )

    @api.constrains("value_input_type", "calc_operand_1_id", "calc_operand_2_id", "calc_operation")
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

            if rec.calc_operand_1_id.value_input_type not in ("numeric", "computed"):
                raise ValidationError("L'opérande 1 doit être numérique ou calculé.")

            if rec.calc_operand_2_id.value_input_type not in ("numeric", "computed"):
                raise ValidationError("L'opérande 2 doit être numérique ou calculé.")

    def compute_option_value(self, values_map):
        """
        values_map = {
            ptav_id: valeur_numérique
        }
        """
        self.ensure_one()

        if self.value_input_type != "computed":
            return values_map.get(self.id)

        left = values_map.get(self.calc_operand_1_id.id, 0.0)
        right = values_map.get(self.calc_operand_2_id.id, 0.0)

        try:
            left = float(left or 0.0)
            right = float(right or 0.0)
        except (TypeError, ValueError):
            left = 0.0
            right = 0.0

        if self.calc_operation == "multiply":
            return left * right

        return 0.0
