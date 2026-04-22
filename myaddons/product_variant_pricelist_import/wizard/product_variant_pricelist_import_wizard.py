# -*- coding: utf-8 -*-

import csv
import io
import os

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProductVariantPricelistImportWizard(models.TransientModel):
    _name = "product.variant.pricelist.import.wizard"
    _description = "Import variantes et pricelist"

    CSV_DIR = "/data/odoo/metal-odoo18-p8179/csv"

    template_id = fields.Many2one(
        "product.template",
        string="Template",
        required=True,
    )

    category_id = fields.Many2one(
        "product.category",
        string="Catégorie",
        required=True,
    )

    attribute_id = fields.Many2one(
        "product.attribute",
        string="Attribut",
        required=True,
        help="Attribut existant. Le module crée seulement les valeurs.",
    )

    pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Pricelist",
        required=True,
    )

    coefficient = fields.Float(
        string="Coefficient",
        default=2.5,
        required=True,
    )

    csv_filename = fields.Selection(
        selection="_selection_csv_files",
        string="Fichier CSV",
        required=True,
    )

    product_secondary_unit_id = fields.Many2one(
        "product.secondary.unit",
        string="Unité de mesure secondaire",
        required=True,
    )

    dependency_type = fields.Selection(
        [
            ("dependent", "Dependent"),
            ("independent", "Independent"),
        ],
        string="Dependency Type",
        default="independent",
        required=True,
    )

    update_standard_price = fields.Boolean(
        string="Mettre à jour le coût d'achat",
        default=True,
    )

    archive_missing_variants = fields.Boolean(
        string="Archiver les variantes absentes du CSV",
        default=False,
    )

    remove_missing_pricelist_items = fields.Boolean(
        string="Supprimer les lignes de pricelist absentes du CSV",
        default=False,
    )

    csv_format_help = fields.Text(
        string="Format CSV attendu",
        compute="_compute_csv_format_help",
    )

    @api.depends("product_secondary_unit_id")
    def _compute_csv_format_help(self):
        for wizard in self:
            lines = [
                "Colonnes obligatoires :",
                "default_code, attribute_value, uom_code, standard_price, meter, factor",
                "",
                "Sens des colonnes :",
                "- default_code : référence produit",
                "- attribute_value : valeur de variante",
                "- uom_code : unité principale Odoo (KG, ML, PI...)",
                "- standard_price : coût dans l'unité principale Odoo",
                "- meter : longueur de référence utilisée pour le calcul",
                "- factor : rapport Odoo par produit pour l'unité secondaire",
                "",
                "Exemple :",
                "default_code,attribute_value,uom_code,standard_price,meter,factor",
                "73309,80,KG,1.0000,6,6.4500",
                "71046,100,KG,0.9999,6,8.7970",
            ]
            if wizard.product_secondary_unit_id:
                lines.extend(
                    [
                        "",
                        f"Unité secondaire choisie dans le wizard : {wizard.product_secondary_unit_id.display_name}",
                    ]
                )
            wizard.csv_format_help = "\n".join(lines)

    @api.model
    def _selection_csv_files(self):
        if not os.path.isdir(self.CSV_DIR):
            return []

        result = []
        for filename in sorted(os.listdir(self.CSV_DIR)):
            full_path = os.path.join(self.CSV_DIR, filename)
            if os.path.isfile(full_path) and filename.lower().endswith(".csv"):
                result.append((filename, filename))
        return result

    def action_import_csv(self):
        self.ensure_one()

        rows = self._read_csv_file()
        if not rows:
            raise UserError(_("Le fichier CSV est vide."))

        required_columns = {
            "default_code",
            "attribute_value",
            "uom_code",
            "standard_price",
            "meter",
            "factor",
        }

        header_keys = set(rows[0].keys())
        missing = required_columns - header_keys
        if missing:
            raise UserError(
                _("Colonnes CSV manquantes : %s") % ", ".join(sorted(missing))
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Import CSV"),
                "message": _(
                    "CSV lu avec succès : %s (%s ligne(s)). "
                    "Unité secondaire : %s. "
                    "Dependency type : %s."
                ) % (
                    self.csv_filename,
                    len(rows),
                    self.product_secondary_unit_id.display_name,
                    dict(self._fields["dependency_type"].selection).get(self.dependency_type),
                ),
                "type": "success",
                "sticky": False,
            },
        }

    def _read_csv_file(self):
        self.ensure_one()

        if not self.csv_filename:
            raise UserError(_("Aucun fichier CSV sélectionné."))

        csv_path = os.path.join(self.CSV_DIR, self.csv_filename)

        if not os.path.isfile(csv_path):
            raise UserError(_("Fichier introuvable : %s") % csv_path)

        try:
            with io.open(csv_path, mode="r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                rows = []
                for row in reader:
                    normalized = {
                        str(k).strip(): (str(v).strip() if v is not None else "")
                        for k, v in row.items()
                    }
                    if any(normalized.values()):
                        rows.append(normalized)
                return rows
        except Exception as exc:
            raise UserError(_("Impossible de lire le fichier CSV : %s") % exc)
