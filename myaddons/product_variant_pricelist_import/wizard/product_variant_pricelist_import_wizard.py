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
                "- attribute_value : valeur d'option / variante",
                "- uom_code : unité principale Odoo (KG, ML, PI...)",
                "- standard_price : coût dans l'unité principale Odoo",
                "- meter : longueur de référence",
                "- factor : rapport Odoo pour l'unité secondaire",
                "",
                "Exemple :",
                "default_code,attribute_value,uom_code,standard_price,meter,factor",
                "71111,HEA 100,KG,1.1500,6,17.6575",
                "71114,HEA 120,KG,1.0400,6,21.0410",
            ]
            if wizard.product_secondary_unit_id:
                lines.append("")
                lines.append(
                    "Unité secondaire choisie : %s"
                    % wizard.product_secondary_unit_id.display_name
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

        self.template_id.categ_id = self.category_id.id

        imported_codes = set()
        created_values = 0
        updated_variants = 0
        created_pricelist_items = 0
        updated_pricelist_items = 0

        for row in rows:
            default_code = self._clean_str(row.get("default_code"))
            attribute_value_name = self._clean_str(row.get("attribute_value"))
            uom_code = self._clean_str(row.get("uom_code"))
            standard_price = self._to_float(row.get("standard_price"))
            factor = self._to_float(row.get("factor"))
            meter = self._to_float(row.get("meter"))

            if not default_code or not attribute_value_name or not uom_code:
                continue

            imported_codes.add(default_code)

            uom = self._get_uom_by_code(uom_code)
            attr_value, value_created = self._get_or_create_attribute_value(attribute_value_name)
            if value_created:
                created_values += 1

            self._sync_template_attribute_line(attr_value)
            self.template_id.invalidate_recordset(["attribute_line_ids", "product_variant_ids"])
            self.template_id._create_variant_ids()

            variant = self._find_variant_from_value(attr_value)
            if not variant:
                raise UserError(
                    _("Impossible de trouver ou créer la variante pour la valeur '%s'.")
                    % attribute_value_name
                )

            self._write_variant_data(
                variant=variant,
                default_code=default_code,
                uom=uom,
                standard_price=standard_price,
                factor=factor,
                meter=meter,
            )
            updated_variants += 1

            item, created = self._create_or_update_pricelist_item(
                variant=variant,
                standard_price=standard_price,
                factor=factor,
            )
            if item:
                if created:
                    created_pricelist_items += 1
                else:
                    updated_pricelist_items += 1

        if self.archive_missing_variants:
            self._archive_missing_variants(imported_codes)

        if self.remove_missing_pricelist_items:
            self._remove_missing_pricelist_items(imported_codes)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Import terminé"),
                "message": _(
                    "Valeurs créées : %(values)s | "
                    "Variantes mises à jour : %(variants)s | "
                    "Lignes pricelist créées : %(pl_create)s | "
                    "Lignes pricelist mises à jour : %(pl_update)s"
                ) % {
                    "values": created_values,
                    "variants": updated_variants,
                    "pl_create": created_pricelist_items,
                    "pl_update": updated_pricelist_items,
                },
                "type": "success",
                "sticky": True,
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

    def _clean_str(self, value):
        return (value or "").strip()

    def _to_float(self, value, default=0.0):
        try:
            return float(str(value or "").replace(",", ".").strip() or default)
        except Exception:
            return default

    def _get_uom_by_code(self, code):
        uom = self.env["uom.uom"].search([("name", "=", code)], limit=1)
        if not uom:
            uom = self.env["uom.uom"].search([("display_name", "=", code)], limit=1)
        if not uom:
            raise UserError(_("Unité introuvable : %s") % code)
        return uom

    def _get_or_create_attribute_value(self, value_name):
        value = self.env["product.attribute.value"].search(
            [
                ("attribute_id", "=", self.attribute_id.id),
                ("name", "=", value_name),
            ],
            limit=1,
        )
        if value:
            return value, False

        value = self.env["product.attribute.value"].create(
            {
                "attribute_id": self.attribute_id.id,
                "name": value_name,
            }
        )
        return value, True

    def _sync_template_attribute_line(self, attr_value):
        self.ensure_one()

        line = self.template_id.attribute_line_ids.filtered(
            lambda l: l.attribute_id.id == self.attribute_id.id
        )[:1]

        if line:
            if attr_value.id not in line.value_ids.ids:
                line.write({"value_ids": [(4, attr_value.id)]})
        else:
            self.template_id.write(
                {
                    "attribute_line_ids": [
                        (
                            0,
                            0,
                            {
                                "attribute_id": self.attribute_id.id,
                                "value_ids": [(6, 0, [attr_value.id])],
                            },
                        )
                    ]
                }
            )

    def _find_variant_from_value(self, attr_value):
        self.ensure_one()

        for variant in self.template_id.product_variant_ids:
            value_ids = variant.product_template_attribute_value_ids.mapped(
                "product_attribute_value_id"
            )
            if attr_value in value_ids:
                return variant
        return False

    def _write_variant_data(self, variant, default_code, uom, standard_price, factor, meter):
        vals = {
            "default_code": default_code,
            "uom_id": uom.id,
            "uom_po_id": uom.id,
        }

        if self.update_standard_price:
            vals["standard_price"] = standard_price

        if "x_meter" in variant._fields:
            vals["x_meter"] = meter

        variant.write(vals)

        self._write_secondary_unit_data(variant, factor)

    def _write_secondary_unit_data(self, variant, factor):
        """
        Écrit l'unité secondaire sur la variante concernée.
        """
        SecondaryLine = None
        line_field_name = None

        if "secondary_unit_ids" in variant._fields:
            SecondaryLine = self.env[variant._fields["secondary_unit_ids"].comodel_name]
            line_field_name = "secondary_unit_ids"
        elif "product_secondary_unit_ids" in variant._fields:
            SecondaryLine = self.env[variant._fields["product_secondary_unit_ids"].comodel_name]
            line_field_name = "product_secondary_unit_ids"

        if not SecondaryLine or not line_field_name:
            # fallback doux : on tente au moins de poser l'unité par défaut si le champ existe
            direct_vals = {}
            if "sale_secondary_uom_id" in variant._fields:
                direct_vals["sale_secondary_uom_id"] = self.product_secondary_unit_id.id
            if "secondary_uom_id" in variant._fields:
                direct_vals["secondary_uom_id"] = self.product_secondary_unit_id.id
            if direct_vals:
                variant.write(direct_vals)
                return

            raise UserError(
                _("Impossible de trouver la relation d'unités secondaires sur la variante '%s'.")
                % variant.display_name
            )

        lines = variant[line_field_name]

        existing = lines.filtered(
            lambda l:
                (
                    "product_id" in l._fields
                    and l.product_id
                    and l.product_id.id == variant.id
                )
                or (
                    "product_variant_id" in l._fields
                    and l.product_variant_id
                    and l.product_variant_id.id == variant.id
                )
                or (
                    "product_tmpl_id" in l._fields
                    and l.product_tmpl_id
                    and l.product_tmpl_id.id == variant.product_tmpl_id.id
                )
        )

        existing = existing.filtered(
            lambda l:
                (
                    "secondary_uom_id" in l._fields
                    and l.secondary_uom_id
                    and l.secondary_uom_id.id == self.product_secondary_unit_id.id
                )
                or (
                    "secondary_unit_id" in l._fields
                    and l.secondary_unit_id
                    and l.secondary_unit_id.id == self.product_secondary_unit_id.id
                )
        )[:1]

        vals = {}

        if "product_id" in SecondaryLine._fields:
            vals["product_id"] = variant.id
        elif "product_variant_id" in SecondaryLine._fields:
            vals["product_variant_id"] = variant.id
        elif "product_tmpl_id" in SecondaryLine._fields:
            vals["product_tmpl_id"] = variant.product_tmpl_id.id

        if "secondary_uom_id" in SecondaryLine._fields:
            vals["secondary_uom_id"] = self.product_secondary_unit_id.id
        elif "secondary_unit_id" in SecondaryLine._fields:
            vals["secondary_unit_id"] = self.product_secondary_unit_id.id

        if "code" in SecondaryLine._fields:
            if hasattr(self.product_secondary_unit_id, "uom_id") and self.product_secondary_unit_id.uom_id:
                vals["code"] = self.product_secondary_unit_id.uom_id.name
            else:
                vals["code"] = self.product_secondary_unit_id.display_name

        if "name" in SecondaryLine._fields:
            vals["name"] = self.product_secondary_unit_id.display_name

        if "factor" in SecondaryLine._fields:
            vals["factor"] = factor
        elif "sale_secondary_uom_factor" in SecondaryLine._fields:
            vals["sale_secondary_uom_factor"] = factor

        if "dependency_type" in SecondaryLine._fields:
            vals["dependency_type"] = self.dependency_type

        if "active" in SecondaryLine._fields:
            vals["active"] = True

        if existing:
            existing.write(vals)
        else:
            variant.write({line_field_name: [(0, 0, vals)]})

        direct_vals = {}
        if "sale_secondary_uom_id" in variant._fields:
            direct_vals["sale_secondary_uom_id"] = self.product_secondary_unit_id.id
        if "secondary_uom_id" in variant._fields:
            direct_vals["secondary_uom_id"] = self.product_secondary_unit_id.id
        if direct_vals:
            variant.write(direct_vals)

    def _create_or_update_pricelist_item(self, variant, standard_price, factor):
        fixed_price = standard_price * factor * self.coefficient

        item = self.env["product.pricelist.item"].search(
            [
                ("pricelist_id", "=", self.pricelist_id.id),
                ("product_id", "=", variant.id),
            ],
            limit=1,
        )

        vals = {
            "pricelist_id": self.pricelist_id.id,
            "applied_on": "0_product_variant",
            "product_id": variant.id,
            "compute_price": "fixed",
            "fixed_price": fixed_price,
        }

        if item:
            item.write(vals)
            return item, False

        return self.env["product.pricelist.item"].create(vals), True

    def _archive_missing_variants(self, imported_codes):
        for variant in self.template_id.product_variant_ids:
            if variant.default_code and variant.default_code not in imported_codes:
                if "active" in variant._fields:
                    variant.active = False

    def _remove_missing_pricelist_items(self, imported_codes):
        items = self.env["product.pricelist.item"].search(
            [
                ("pricelist_id", "=", self.pricelist_id.id),
                ("product_id", "!=", False),
                ("product_tmpl_id", "=", False),
            ]
        )
        for item in items:
            if item.product_id.product_tmpl_id == self.template_id:
                if item.product_id.default_code not in imported_codes:
                    item.unlink()
