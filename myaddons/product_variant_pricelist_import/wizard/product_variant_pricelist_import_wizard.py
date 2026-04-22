
# -*- coding: utf-8 -*-

import base64
import csv
import io

from odoo import _, fields, models
from odoo.exceptions import UserError


class ProductVariantPricelistImportWizard(models.TransientModel):
    _name = "product.variant.pricelist.import.wizard"
    _description = "Import variantes et pricelist"

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

    csv_file = fields.Binary(
        string="Fichier CSV",
        required=True,
    )

    csv_filename = fields.Char(
        string="Nom du fichier",
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

    def action_import_csv(self):
        self.ensure_one()

        rows = self._read_csv_file()
        if not rows:
            raise UserError(_("Le fichier CSV est vide."))

        # Pour ce premier jet on vérifie juste la structure
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
                    "CSV lu avec succès. %s ligne(s) détectée(s). "
                    "La logique d'import complète sera branchée à l'étape suivante."
                ) % len(rows),
                "type": "success",
                "sticky": False,
            },
        }

    def _read_csv_file(self):
        self.ensure_one()

        if not self.csv_file:
            raise UserError(_("Aucun fichier CSV fourni."))

        try:
            decoded = base64.b64decode(self.csv_file)
            content = decoded.decode("utf-8-sig")
        except Exception as exc:
            raise UserError(_("Impossible de lire le fichier CSV : %s") % exc)

        buffer = io.StringIO(content)
        reader = csv.DictReader(buffer)
        rows = []

        for row in reader:
            normalized = {str(k).strip(): (str(v).strip() if v is not None else "") for k, v in row.items()}
            if any(normalized.values()):
                rows.append(normalized)

        return rows
