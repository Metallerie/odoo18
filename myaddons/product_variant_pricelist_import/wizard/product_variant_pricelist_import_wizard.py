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

    @api.model
    def _selection_csv_files(self):
        csv_dir = self.CSV_DIR
        if not os.path.isdir(csv_dir):
            return []

        files = []
        for filename in sorted(os.listdir(csv_dir)):
            full_path = os.path.join(csv_dir, filename)
            if os.path.isfile(full_path) and filename.lower().endswith(".csv"):
                files.append((filename, filename))
        return files

    def action_import_csv(self):
        self.ensure_one()

        rows = self._read_csv_file()
        if not rows:
            raise UserError(_("Le fichier CSV est vide."))

        required_columns = {
            "default_code",
            "attribute_value",
            "uom_id",
            "factor",
            "standard_price",
            "sale_secondary_uom_code",
        }
        missing = required_columns - set(rows[0].keys())
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
                    "La logique d'import complète sera branchée ensuite."
                ) % (self.csv_filename, len(rows)),
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
