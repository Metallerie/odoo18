# -*- coding: utf-8 -*-
# models.py

import re
import unicodedata

from odoo import api, fields, models
from odoo.exceptions import ValidationError


def format_variable_code(value):
    value = value or ""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9_]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_").lower()


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    is_calculated = fields.Boolean(string="Attribut calculé", default=False)

    calc_method = fields.Selection(
        [
            ("tube_cut_total_length", "Tube : longueur totale coupée"),
            ("sheet_laser_cut", "Tôle : découpe laser"),
        ],
        string="Méthode de calcul",
    )

    use_as_order_qty = fields.Boolean(string="Utiliser comme quantité de commande", default=False)
    affect_price = fields.Boolean(string="Affecte le prix", default=False)
    show_result_in_cart = fields.Boolean(string="Afficher le résultat dans le panier", default=True)
    result_readonly = fields.Boolean(string="Résultat en lecture seule", default=True)

    @api.onchange("is_calculated")
    def _onchange_is_calculated(self):
        for rec in self:
            if not rec.is_calculated:
                rec.calc_method = False
                rec.use_as_order_qty = False
                rec.affect_price = False
                rec.show_result_in_cart = True
                rec.result_readonly = True

    @api.constrains("is_calculated", "calc_method")
    def _check_calculated_attribute(self):
        for rec in self:
            if rec.is_calculated and not rec.calc_method:
                raise ValidationError("Un attribut calculé doit avoir une méthode de calcul.")


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

    numeric_type = fields.Selection(
        [
            ("int", "Entier"),
            ("float", "Décimal"),
        ],
        string="Type numérique",
        default="float",
    )

    is_free_text = fields.Boolean(string="Texte libre", default=False)

    @api.onchange("value_input_type")
    def _onchange_value_input_type(self):
        for rec in self:
            if rec.value_input_type != "numeric":
                rec.numeric_type = "float"


class ProductOptionVariable(models.Model):
    _name = "product.option.variable"
    _description = "Variable de calcul"
    _order = "code, id"

    name = fields.Char(string="Nom", required=True)

    code = fields.Char(
        string="Code calcul",
        required=True,
        help="Nom technique utilisé dans les formules. Exemple : coef, densite, standard_price_par_ml.",
    )

    variable_type = fields.Selection(
        [
            ("numeric", "Numérique"),
            ("text", "Texte"),
        ],
        string="Type",
        default="numeric",
        required=True,
    )

    note = fields.Char(string="Note")

    @api.onchange("name")
    def _onchange_name_generate_code(self):
        for rec in self:
            if rec.name and not rec.code:
                rec.code = format_variable_code(rec.name)

    @api.onchange("code")
    def _onchange_code_format(self):
        for rec in self:
            if rec.code:
                rec.code = format_variable_code(rec.code)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code"):
                vals["code"] = format_variable_code(vals["code"])
            elif vals.get("name"):
                vals["code"] = format_variable_code(vals["name"])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("code"):
            vals["code"] = format_variable_code(vals["code"])
        return super().write(vals)

    _sql_constraints = [
        (
            "unique_product_option_variable_code",
            "unique(code)",
            "Ce code de variable existe déjà.",
        )
    ]


class ProductTemplate(models.Model):
    _inherit = "product.template"

    calculated_option_line_ids = fields.One2many(
        "product.template.calculated.option.line",
        "product_tmpl_id",
        string="Dépendances des options calculées",
    )


class ProductTemplateAttributeLine(models.Model):
    _inherit = "product.template.attribute.line"

    def action_open_value_variables(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Variables des valeurs : %s" % self.attribute_id.display_name,
            "res_model": "product.template.attribute.value.variable",
            "view_mode": "list,form",
            "target": "new",
            "domain": [
                ("product_tmpl_id", "=", self.product_tmpl_id.id),
                ("attribute_id", "=", self.attribute_id.id),
            ],
            "context": {
                "default_product_tmpl_id": self.product_tmpl_id.id,
                "default_attribute_id": self.attribute_id.id,
            },
        }


class ProductTemplateAttributeValueVariable(models.Model):
    _name = "product.template.attribute.value.variable"
    _description = "Variable par valeur d'attribut et par produit"
    _order = "product_tmpl_id, attribute_id, value_id, variable_id"

    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Produit",
        required=True,
        ondelete="cascade",
    )

    attribute_id = fields.Many2one(
        "product.attribute",
        string="Attribut",
        required=True,
        ondelete="restrict",
    )

    available_value_ids = fields.Many2many(
        "product.attribute.value",
        string="Valeurs disponibles",
        compute="_compute_available_value_ids",
    )

    value_id = fields.Many2one(
        "product.attribute.value",
        string="Valeur",
        required=True,
        ondelete="restrict",
        domain="[('id', 'in', available_value_ids)]",
    )

    variable_id = fields.Many2one(
        "product.option.variable",
        string="Variable",
        required=True,
        ondelete="restrict",
    )

    variable_code = fields.Char(
        related="variable_id.code",
        string="Code",
        store=True,
        readonly=True,
    )

    variable_type = fields.Selection(
        related="variable_id.variable_type",
        string="Type",
        store=True,
        readonly=True,
    )

    numeric_value = fields.Float(string="Valeur numérique")
    text_value = fields.Char(string="Valeur texte")

    @api.depends("product_tmpl_id", "attribute_id")
    def _compute_available_value_ids(self):
        for rec in self:
            values = self.env["product.attribute.value"]
            if rec.product_tmpl_id and rec.attribute_id:
                line = rec.product_tmpl_id.attribute_line_ids.filtered(
                    lambda l: l.attribute_id == rec.attribute_id
                )[:1]
                values = line.value_ids if line else values
            rec.available_value_ids = values

    @api.onchange("variable_id")
    def _onchange_variable_id(self):
        for rec in self:
            if rec.variable_type == "numeric":
                rec.text_value = False
            elif rec.variable_type == "text":
                rec.numeric_value = 0.0

    @api.constrains("product_tmpl_id", "attribute_id", "value_id")
    def _check_consistency(self):
        for rec in self:
            product_attribute_ids = rec.product_tmpl_id.attribute_line_ids.mapped("attribute_id").ids
            if rec.attribute_id.id not in product_attribute_ids:
                raise ValidationError("L'attribut doit être présent sur le produit.")

            if rec.value_id.attribute_id != rec.attribute_id:
                raise ValidationError("La valeur ne correspond pas à l'attribut.")

            allowed_values = rec.product_tmpl_id.attribute_line_ids.filtered(
                lambda l: l.attribute_id == rec.attribute_id
            ).mapped("value_ids")

            if rec.value_id not in allowed_values:
                raise ValidationError("La valeur doit être présente sur la ligne d'attribut du produit.")

    _sql_constraints = [
        (
            "unique_product_attribute_value_variable",
            "unique(product_tmpl_id, attribute_id, value_id, variable_id)",
            "Cette variable existe déjà pour cette valeur sur ce produit.",
        )
    ]


class ProductTemplateCalculatedOptionLine(models.Model):
    _name = "product.template.calculated.option.line"
    _description = "Dépendance d'option calculée par produit"
    _order = "product_tmpl_id, calculated_attribute_id, sequence, id"

    sequence = fields.Integer(string="Séquence", default=10)

    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Produit",
        required=True,
        ondelete="cascade",
    )

    calculated_attribute_id = fields.Many2one(
        "product.attribute",
        string="Attribut calculé",
        required=True,
        domain="[('is_calculated', '=', True)]",
        ondelete="restrict",
    )

    available_source_attribute_ids = fields.Many2many(
        "product.attribute",
        string="Attributs disponibles",
        compute="_compute_available_source_attribute_ids",
    )

    source_attribute_id = fields.Many2one(
        "product.attribute",
        string="Attribut source",
        required=True,
        domain="[('id', 'in', available_source_attribute_ids)]",
        ondelete="restrict",
    )

    source_value_input_type = fields.Selection(
        [
            ("text", "Texte"),
            ("numeric", "Numérique"),
            ("computed", "Calculé"),
        ],
        string="Type",
        compute="_compute_source_infos",
        store=True,
    )

    source_numeric_type = fields.Selection(
        [
            ("int", "Entier"),
            ("float", "Décimal"),
        ],
        string="Type numérique",
        compute="_compute_source_infos",
        store=True,
    )

    source_is_free_text = fields.Boolean(
        string="Texte libre",
        compute="_compute_source_infos",
        store=True,
    )

    role = fields.Char(
        string="Rôle",
        help="Exemple : nombre_piece, longueur, largeur, epaisseur, materiau.",
    )

    @api.depends(
        "product_tmpl_id",
        "product_tmpl_id.attribute_line_ids",
        "product_tmpl_id.attribute_line_ids.attribute_id",
    )
    def _compute_available_source_attribute_ids(self):
        for rec in self:
            rec.available_source_attribute_ids = rec.product_tmpl_id.attribute_line_ids.mapped("attribute_id")

    @api.depends(
        "source_attribute_id",
        "source_attribute_id.value_ids.value_input_type",
        "source_attribute_id.value_ids.numeric_type",
        "source_attribute_id.value_ids.is_free_text",
    )
    def _compute_source_infos(self):
        for rec in self:
            first_value = rec.source_attribute_id.value_ids[:1]
            rec.source_value_input_type = first_value.value_input_type if first_value else False
            rec.source_numeric_type = first_value.numeric_type if first_value else False
            rec.source_is_free_text = first_value.is_free_text if first_value else False

    @api.constrains("product_tmpl_id", "calculated_attribute_id", "source_attribute_id")
    def _check_line_consistency(self):
        for rec in self:
            if rec.source_attribute_id == rec.calculated_attribute_id:
                raise ValidationError("Un attribut calculé ne peut pas dépendre de lui-même.")

            product_attribute_ids = rec.product_tmpl_id.attribute_line_ids.mapped("attribute_id").ids

            if rec.source_attribute_id.id not in product_attribute_ids:
                raise ValidationError("L'attribut source doit être présent sur le produit.")
