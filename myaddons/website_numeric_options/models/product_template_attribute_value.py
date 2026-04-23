# models/product_attribute_value.py
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductAttributeValue(models.Model):
    
    _inherit = "product.template.attribute.value"
    
    value_input_type = fields.Selection(
        [
            ("text", "Texte"),
            ("numeric", "Numérique"),
            ("computed", "Calculé"),
        ],
        string="Type de saisie",
        default="text",
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
        domain="[('id', '!=', id)]",
    )

    calc_operand_2_id = fields.Many2one(
        "product.attribute.value",
        string="Opérande 2",
        domain="[('id', '!=', id), ('id', '!=', calc_operand_1_id)]",
    )

    is_computed_readonly = fields.Boolean(
        string="Résultat en lecture seule",
        default=True,
    )

    @api.constrains("value_input_type", "calc_operation", "calc_operand_1_id", "calc_operand_2_id")
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
