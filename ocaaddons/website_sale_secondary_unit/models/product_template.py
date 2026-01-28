# -*- coding: utf-8 -*-
# Odoo 18 – website_sale_secondary_unit
# DEBUG version with explicit logs

import logging
from odoo import fields, models

_logger = logging.getLogger(__name__)


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
        info = super()._get_combination_info(
            combination=combination,
            product_id=product_id,
            add_qty=add_qty,
            parent_combination=parent_combination,
            only_template=only_template,
        )

        _logger.info("=== SECONDARY UOM DEBUG ===")
        _logger.info("Template ID: %s", self.id)
        _logger.info("Product ID: %s", product_id)
        _logger.info("Base price (primary): %s", info.get("price"))

        tmpl = self.sudo()
        product = False

        # 1) SOURCE PRINCIPALE : TEMPLATE
        sale_secondary = tmpl.sale_secondary_uom_id
        _logger.info("Template sale_secondary_uom_id: %s", sale_secondary)

        # 2) VARIANTE (si champ existe vraiment)
        if product_id:
            product = self.env["product.product"].browse(product_id).sudo()
            if hasattr(product, "sale_secondary_uom_id"):
                _logger.info(
                    "Variant sale_secondary_uom_id: %s",
                    product.sale_secondary_uom_id,
                )
                if product.sale_secondary_uom_id:
                    sale_secondary = product.sale_secondary_uom_id

        has_secondary = bool(sale_secondary)
        info["has_secondary_uom"] = has_secondary
        _logger.info("HAS secondary uom: %s", has_secondary)

        if not has_secondary:
            _logger.warning("NO secondary UOM FOUND -> nothing injected")
            return info

        # 3) DONNÉES SECONDARY
        su = sale_secondary.sudo()
        factor = su.factor or 0.0

        primary_uom_name = (
            product.uom_id.sudo().name
            if product
            else tmpl.uom_id.sudo().name
        )

        price_primary = float(info.get("price") or 0.0)
        price_secondary = price_primary * factor

        _logger.info("Secondary UOM ID: %s", su.id)
        _logger.info("Secondary UOM name: %s", su.uom_id.sudo().name)
        _logger.info("Primary UOM name: %s", primary_uom_name)
        _logger.info("Factor (secondary -> primary): %s", factor)
        _logger.info("Price secondary: %s", price_secondary)

        info.update(
            {
                "sale_secondary_uom_id": su.id,
                "sale_secondary_uom_name": su.uom_id.sudo().name,
                "sale_secondary_rounding": su.uom_id.sudo().rounding,
                "sale_secondary_factor": factor,
                "primary_uom_name": primary_uom_name,
                "price_primary_uom": price_primary,
                "price_secondary_uom": price_secondary,
            }
        )

        _logger.info("=== END SECONDARY UOM DEBUG ===")
        return info
