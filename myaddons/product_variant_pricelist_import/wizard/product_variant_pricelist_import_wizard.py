# -*- coding: utf-8 -*-

# product_variant_pricelist_import_wizard.py

import csv
import io
import os
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProductVariantPricelistImportWizard(models.TransientModel):
    _name = "product.variant.pricelist.import.wizard"
    _description = "Import variantes et pricelist"

    CSV_DIR = "/data/odoo/metal-odoo18-p8179/csv"

    template_id = fields.Many2one("product.template", string="Template", required=True)
    category_id = fields.Many2one("product.category", string="Catégorie", required=True)
    attribute_id = fields.Many2one("product.attribute", string="Attribut", required=True)
    pricelist_id = fields.Many2one("product.pricelist", string="Pricelist", required=True)

    coefficient = fields.Float(string="Coefficient", default=2.5, required=True)

    csv_filename = fields.Selection(
        selection="_selection_csv_files",
        string="Fichier CSV",
        required=True,
    )

    product_secondary_uom_id = fields.Many2one(
        "uom.uom",
        string="Unité de mesure secondaire",
        required=False,
        help="Laisse vide si achat et vente sont dans la même unité.",
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

    @api.depends("product_secondary_uom_id")
    def _compute_csv_format_help(self):
        for wizard in self:
            wizard.csv_format_help = "\n".join(
                [
                    "Colonnes obligatoires :",
                    "default_code,name,uom_code,standard_price,factor,purchase_unit",
                    "",
                    "Colonnes optionnelles :",
                    "height,width,length,diameter,thickness,attribute_value",
                    "",
                    "Règle importante :",
                    "- si default_code existe déjà dans le template, la variante est mise à jour",
                    "- aucune option n'est créée si la variante existe déjà",
                    "- si default_code existe sur un autre template, l'import est bloqué",
                    "- si default_code n'existe pas, la variante est créée via l'attribut",
                    "- l'unité principale du produit n'est jamais modifiée",
                    "",
                    "Calcul coût d'achat :",
                    "standard_price Odoo = standard_price CSV / product_length",
                    "",
                    "Calcul prix de vente :",
                    "prix vente ML = standard_price Odoo × coefficient",
                    "",
                    "purchase_unit sert à créer le conditionnement.",
                    "Exemple : purchase_unit=Tube et factor=6.15 => 1 Tube = 6.15 ML",
                ]
            )

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
            "name",
            "uom_code",
            "standard_price",
            "factor",
            "purchase_unit",
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
        created_variants = 0
        updated_variants = 0
        created_pricelist_items = 0
        updated_pricelist_items = 0
        created_packagings = 0
        updated_packagings = 0

        for row in rows:
            default_code = self._clean_str(row.get("default_code"))
            product_name = self._clean_str(row.get("name"))

            supplier_price = self._to_float(row.get("standard_price"))
            factor = self._to_float(row.get("factor"), default=1.0)
            purchase_unit = self._clean_str(row.get("purchase_unit")) or "Barre"

            dimensions = self._extract_dimensions_from_row(row)

            if not default_code or not product_name:
                continue

            imported_codes.add(default_code)

            variant = self._find_variant_by_default_code_in_template(default_code)

            if variant:
                updated_variants += 1

            else:
                other_variant = self._find_variant_by_default_code_other_template(default_code)
                if other_variant:
                    raise UserError(
                        _(
                            "La référence %s existe déjà sur un autre template : %s.\n"
                            "Import bloqué pour éviter de créer une mauvaise option."
                        )
                        % (default_code, other_variant.product_tmpl_id.display_name)
                    )

                attribute_value_name = self._get_attribute_value_from_row(row)
                if not attribute_value_name:
                    raise UserError(
                        _("Impossible de créer la variante %s : attribut introuvable.")
                        % default_code
                    )

                attr_value, value_created = self._get_or_create_attribute_value(
                    attribute_value_name
                )
                if value_created:
                    created_values += 1

                self._sync_template_attribute_line(attr_value)

                self.template_id.invalidate_recordset(
                    ["attribute_line_ids", "product_variant_ids"]
                )
                self.template_id._create_variant_ids()

                variant = self._find_variant_from_value(attr_value)
                if not variant:
                    raise UserError(
                        _("Impossible de trouver ou créer la variante pour la valeur '%s'.")
                        % attribute_value_name
                    )

                created_variants += 1

            product_length = self._get_product_length_for_price_from_dimensions(
                variant=variant,
                dimensions=dimensions,
                factor=factor,
            )

            standard_price_ml = (
                supplier_price / product_length if product_length else supplier_price
            )

            self._write_variant_data(
                variant=variant,
                default_code=default_code,
                standard_price=standard_price_ml,
                factor=factor,
                dimensions=dimensions,
            )

            packaging, packaging_created = self._create_or_update_packaging(
                variant=variant,
                name=purchase_unit,
                qty=factor,
            )

            if packaging_created:
                created_packagings += 1
            else:
                updated_packagings += 1

            pricelist_item, created = self._create_or_update_pricelist_item(
                variant=variant,
                standard_price=standard_price_ml,
            )

            if created:
                created_pricelist_items += 1
            else:
                updated_pricelist_items += 1

        if self.archive_missing_variants:
            self._archive_missing_variants(imported_codes)

        if self.remove_missing_pricelist_items:
            self._remove_missing_pricelist_items(imported_codes)
            
        self.template_id.last_variant_import_date = fields.Datetime.now()
        
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Import terminé"),
                "message": _(
                    "Valeurs créées : %(values)s | "
                    "Variantes créées : %(variants_create)s | "
                    "Variantes mises à jour : %(variants_update)s | "
                    "Conditionnements créés : %(pack_create)s | "
                    "Conditionnements mis à jour : %(pack_update)s | "
                    "Pricelist créées : %(pl_create)s | "
                    "Pricelist mises à jour : %(pl_update)s"
                )
                % {
                    "values": created_values,
                    "variants_create": created_variants,
                    "variants_update": updated_variants,
                    "pack_create": created_packagings,
                    "pack_update": updated_packagings,
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
                        if k is not None
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
            value = str(value or "").replace(",", ".").strip()
            if not value:
                return default
            return float(value)
        except Exception:
            return default

    def _get_attribute_value_from_row(self, row):
        value = self._clean_str(row.get("attribute_value"))
        if value:
            return value

        name = self._clean_str(row.get("name"))
        match = re.search(
            r"(\d+(?:[.,]\d+)?)x(\d+(?:[.,]\d+)?)x(\d+(?:[.,]\d+)?)",
            name,
            re.IGNORECASE,
        )
        if match:
            a = match.group(1).replace(",", ".")
            b = match.group(2).replace(",", ".")
            c = match.group(3).replace(",", ".")
            return "%sX%sx%s mm" % (a, b, c)

        return name

    def _extract_dimensions_from_row(self, row):
        return {
            "product_height": self._to_float(row.get("height")),
            "product_width": self._to_float(row.get("width")),
            "product_length": self._to_float(row.get("length")),
            "product_diameter": self._to_float(row.get("diameter")),
            "product_thickness": self._to_float(row.get("thickness")),
        }

    def _find_variant_by_default_code_in_template(self, default_code):
        return self.env["product.product"].search(
            [
                ("default_code", "=", default_code),
                ("product_tmpl_id", "=", self.template_id.id),
            ],
            limit=1,
        )

    def _find_variant_by_default_code_other_template(self, default_code):
        return self.env["product.product"].search(
            [
                ("default_code", "=", default_code),
                ("product_tmpl_id", "!=", self.template_id.id),
            ],
            limit=1,
        )

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
            lambda line: line.attribute_id.id == self.attribute_id.id
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

        self.template_id.invalidate_recordset(["product_variant_ids"])

        for variant in self.template_id.product_variant_ids:
            value_ids = variant.product_template_attribute_value_ids.mapped(
                "product_attribute_value_id"
            )
            if attr_value in value_ids:
                return variant

        return False

    def _write_variant_data(
        self,
        variant,
        default_code,
        standard_price,
        factor,
        dimensions=None,
    ):
        vals = {
            "default_code": default_code,
        }

        if self.update_standard_price:
            vals["standard_price"] = standard_price

        if "product_factor" in variant._fields:
            vals["product_factor"] = factor

        if dimensions:
            for field_name, value in dimensions.items():
                if field_name in variant._fields:
                    vals[field_name] = value

        vals.pop("uom_id", None)
        vals.pop("uom_po_id", None)

        variant.write(vals)

        template_vals = {}
        if dimensions:
            for field_name, value in dimensions.items():
                if field_name in variant.product_tmpl_id._fields:
                    template_vals[field_name] = value

        template_vals.pop("uom_id", None)
        template_vals.pop("uom_po_id", None)

        if template_vals:
            variant.product_tmpl_id.write(template_vals)

        if self.product_secondary_uom_id:
            self._write_secondary_unit_data(variant, factor)

    def _create_or_update_packaging(self, variant, name, qty):
        ProductPackaging = self.env["product.packaging"]

        packaging = ProductPackaging.search(
            [
                ("product_id", "=", variant.id),
                ("name", "=", name),
            ],
            limit=1,
        )

        vals = {
            "name": name,
            "product_id": variant.id,
            "qty": qty,
        }

        if "purchase" in ProductPackaging._fields:
            vals["purchase"] = True

        if "sales" in ProductPackaging._fields:
            vals["sales"] = False

        if packaging:
            packaging.write(vals)
            return packaging, False

        return ProductPackaging.create(vals), True

    def _write_secondary_unit_data(self, variant, factor):
        SecondaryUnit = self.env["product.secondary.unit"]

        existing = SecondaryUnit.search(
            [
                ("product_tmpl_id", "=", variant.product_tmpl_id.id),
                ("product_id", "=", variant.id),
                ("uom_id", "=", self.product_secondary_uom_id.id),
            ],
            limit=1,
        )

        vals = {
            "name": self.product_secondary_uom_id.display_name,
            "code": self.product_secondary_uom_id.name,
            "product_tmpl_id": variant.product_tmpl_id.id,
            "product_id": variant.id,
            "uom_id": self.product_secondary_uom_id.id,
            "dependency_type": self.dependency_type,
            "factor": factor,
            "active": True,
        }

        if existing:
            existing.write(vals)
            secondary_line = existing
        else:
            secondary_line = SecondaryUnit.create(vals)

        product_vals = {}

        if "sale_secondary_uom_id" in variant._fields:
            product_vals["sale_secondary_uom_id"] = secondary_line.id

        if "purchase_secondary_uom_id" in variant._fields:
            product_vals["purchase_secondary_uom_id"] = secondary_line.id

        if "secondary_uom_id" in variant._fields:
            product_vals["secondary_uom_id"] = secondary_line.id

        product_vals.pop("uom_id", None)
        product_vals.pop("uom_po_id", None)

        if product_vals:
            variant.write(product_vals)

        template_vals = {}

        if "sale_secondary_uom_id" in variant.product_tmpl_id._fields:
            template_vals["sale_secondary_uom_id"] = secondary_line.id

        if "purchase_secondary_uom_id" in variant.product_tmpl_id._fields:
            template_vals["purchase_secondary_uom_id"] = secondary_line.id

        if "secondary_uom_id" in variant.product_tmpl_id._fields:
            template_vals["secondary_uom_id"] = secondary_line.id

        template_vals.pop("uom_id", None)
        template_vals.pop("uom_po_id", None)

        if template_vals:
            variant.product_tmpl_id.write(template_vals)

    def _get_product_length_for_price_from_dimensions(
        self,
        variant,
        dimensions=None,
        factor=1.0,
    ):
        dimensions = dimensions or {}

        product_length = dimensions.get("product_length")
        if product_length:
            return product_length

        if "product_length" in variant._fields and variant.product_length:
            return variant.product_length

        if (
            variant.product_tmpl_id
            and "product_length" in variant.product_tmpl_id._fields
            and variant.product_tmpl_id.product_length
        ):
            return variant.product_tmpl_id.product_length

        return factor or 1.0

    def _create_or_update_pricelist_item(self, variant, standard_price):
        fixed_price = standard_price * self.coefficient

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
