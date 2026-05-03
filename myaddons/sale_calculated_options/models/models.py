# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    is_calculated = fields.Boolean(
        string="Attribut calculé",
        default=False,
    )

    calc_method = fields.Selection(
        [
            ("tube_cut_total_length", "Tube : longueur totale coupée"),
            ("sheet_laser_cut", "Tôle : découpe laser"),
        ],
        string="Méthode de calcul",
    )

    calculation_line_ids = fields.One2many(
        "product.attribute.calculation.line",
        "calculated_attribute_id",
        string="Attributs nécessaires",
    )

    use_as_order_qty = fields.Boolean(
        string="Utiliser comme quantité de commande",
        default=False,
    )

    affect_price = fields.Boolean(
        string="Affecte le prix",
        default=False,
    )

    show_result_in_cart = fields.Boolean(
        string="Afficher le résultat dans le panier",
        default=True,
    )

    result_readonly = fields.Boolean(
        string="Résultat en lecture seule",
        default=True,
    )

    @api.constrains("is_calculated", "calc_method", "calculation_line_ids")
    def _check_calculated_attribute(self):
        for rec in self:
            if not rec.is_calculated:
                continue

            if not rec.calc_method:
                raise ValidationError(
                    "Un attribut calculé doit avoir une méthode de calcul."
                )

            if not rec.calculation_line_ids:
                raise ValidationError(
                    "Un attribut calculé doit avoir au moins un attribut nécessaire."
                )

            for line in rec.calculation_line_ids:
                if line.source_attribute_id == rec:
                    raise ValidationError(
                        "Un attribut calculé ne peut pas dépendre de lui-même."
                    )

    @api.onchange("is_calculated")
    def _onchange_is_calculated(self):
        for rec in self:
            if not rec.is_calculated:
                rec.calc_method = False
                rec.use_as_order_qty = False
                rec.affect_price = False
                rec.show_result_in_cart = True
                rec.result_readonly = True

    def compute_calculated_value(self, values_map):
        """
        values_map attendu :
        {
            attribute_id: value,
            ...
        }
        """
        self.ensure_one()

        if not self.is_calculated or not self.calc_method:
            return False

        if self.calc_method == "tube_cut_total_length":
            return self._compute_tube_cut_total_length(values_map)

        if self.calc_method == "sheet_laser_cut":
            return self._compute_sheet_laser_cut(values_map)

        return False

    def _get_numeric_value_from_map(self, values_map, source_attribute):
        value = values_map.get(source_attribute.id, 0.0)

        try:
            return float(str(value or "0").replace(",", "."))
        except (TypeError, ValueError):
            return 0.0

    def _compute_tube_cut_total_length(self, values_map):
        """
        Méthode tube :
        nombre de pièces × longueur
        """
        self.ensure_one()

        result = 1.0

        for line in self.calculation_line_ids.sorted("sequence"):
            result *= self._get_numeric_value_from_map(
                values_map,
                line.source_attribute_id,
            )

        return result

    def _compute_sheet_laser_cut(self, values_map):
        """
        Première version simple :
        multiplication des attributs nécessaires.

        Exemple :
        nombre × longueur × largeur × épaisseur

        On affinera après pour retourner aussi prix, poids, note, etc.
        """
        self.ensure_one()

        result = 1.0

        for line in self.calculation_line_ids.sorted("sequence"):
            result *= self._get_numeric_value_from_map(
                values_map,
                line.source_attribute_id,
            )

        return result


class ProductAttributeCalculationLine(models.Model):
    _name = "product.attribute.calculation.line"
    _description = "Ligne de dépendance d'attribut calculé"
    _order = "sequence, id"

    sequence = fields.Integer(
        string="Séquence",
        default=10,
    )

    calculated_attribute_id = fields.Many2one(
        "product.attribute",
        string="Attribut calculé",
        required=True,
        ondelete="cascade",
    )

    source_attribute_id = fields.Many2one(
        "product.attribute",
        string="Attribut nécessaire",
        required=True,
        ondelete="restrict",
    )

    role = fields.Char(
        string="Rôle",
        help="Exemple : nombre_piece, longueur, largeur, epaisseur.",
    )
