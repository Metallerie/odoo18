# -*- coding: utf-8 -*-
# Copyright 2019 Tecnativa - Sergio Teruel
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    allow_uom_sell = fields.Boolean(
        string="Allow to sell in unit of measure",
        default=True,
    )

    def _get_combination_info(
        self,
        combination=False,
        product_id=False,
        add_qty=1,
        parent_combination=False,
        only_template=False,
    ):
        combination_info = super()._get_combination_info(
            combination=combination,
            product_id=product_id,
            add_qty=add_qty,
            parent_combination=parent_combination,
            only_template=only_template,
        )

        # Variant-first (website doit se baser sur product.product)
        product = self.env["product.product"].browse(product_id) if product_id else self.env["product.product"]
        product_sudo = product.sudo() if product_id else False
        tmpl_sudo = self.sudo()

        sale_secondary = False
        if product_sudo and product_sudo.exists():
            sale_secondary = product_sudo.sale_secondary_uom_id
        if not sale_secondary:
            sale_secondary = tmpl_sudo.sale_secondary_uom_id

        has_secondary = bool(sale_secondary)
        combination_info.update({"has_secondary_uom": has_secondary})

        if has_secondary:
            su = sale_secondary.sudo()

            # UoM names doivent être accessibles au public => sudo
            secondary_uom_name = su.uom_id.sudo().name  # ex: ML
            primary_uom_name = (
                product_sudo.uom_id.sudo().name if product_sudo else tmpl_sudo.uom_id.sudo().name
            )  # ex: KG

            factor = su.factor or 0.0  # kg par ML (chez toi)

            # price = prix de vente unitaire Odoo (dans l'UoM primaire, souvent KG)
            price_primary = float(combination_info.get("price") or 0.0)
            price_secondary = price_primary * factor

            combination_info.update(
                {
                    "sale_secondary_uom_id": su.id,
                    "sale_secondary_uom_name": secondary_uom_name,
                    "sale_secondary_rounding": su.uom_id.sudo().rounding,
                    "sale_secondary_factor": factor,
                    "primary_uom_name": primary_uom_name,
                    "price_primary_uom": price_primary,      # €/KG
                    "price_secondary_uom": price_secondary,  # €/ML
                }
            )

        return combination_info
