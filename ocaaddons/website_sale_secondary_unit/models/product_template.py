# -*- coding: utf-8 -*-
# ocaaddons/website_sale_secondary_unit/models/product_template.py
#
# Patch Métallerie (Odoo 18):
# - Injecte les infos d'unité secondaire dans combination_info
# - ET SURTOUT: remplace combination_info['price'] par le prix en unité secondaire
#   pour que le JS standard de website_sale mette à jour le prix à chaque changement de variante.
#
from odoo import fields, models
import logging

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
        combination_info = super()._get_combination_info(
            combination=combination,
            product_id=product_id,
            add_qty=add_qty,
            parent_combination=parent_combination,
            only_template=only_template,
        )

        tmpl = self.sudo()
        product = self.env["product.product"].browse(product_id) if product_id else self.env["product.product"]
        product_sudo = product.sudo() if product_id else False

        # ========= DEBUG HEADER =========
        _logger.info("=== WSU DEBUG (product.template._get_combination_info) ===")
        _logger.info(
            "tmpl=%s (%s) product_id(arg)=%s add_qty=%s only_template=%s",
            tmpl.display_name,
            tmpl.id,
            product_id,
            add_qty,
            only_template,
        )
        if product_sudo and product_sudo.exists():
            _logger.info("picked product=%s (%s)", product_sudo.display_name, product_sudo.id)
        else:
            _logger.info("picked product=<none>")

        # ========= pick secondary unit (variant-first) =========
        sale_secondary = False
        if product_sudo and product_sudo.exists():
            sale_secondary = product_sudo.sale_secondary_uom_id
        if not sale_secondary:
            sale_secondary = tmpl.sale_secondary_uom_id

        _logger.info("variant sale_secondary_uom_id=%s", product_sudo.sale_secondary_uom_id.ids if product_sudo else None)
        _logger.info("template sale_secondary_uom_id=%s", tmpl.sale_secondary_uom_id.ids)

        has_secondary = bool(sale_secondary)
        combination_info["has_secondary_uom"] = has_secondary
        _logger.info("HAS secondary uom=%s", has_secondary)

        if not has_secondary:
            _logger.warning("NO secondary UOM FOUND -> nothing injected")
            _logger.info("=== END WSU DEBUG ===")
            return combination_info

        su = sale_secondary.sudo()

        # Names: public website => sudo
        secondary_uom_name = su.uom_id.sudo().name or ""
        primary_uom_name = (
            (product_sudo.uom_id.sudo().name if product_sudo and product_sudo.exists() else tmpl.uom_id.sudo().name)
            or ""
        )

        # Factor: chez toi = "kg par ML" (primary per secondary)
        factor = float(su.factor or 0.0)

        # Base price as returned by website_sale (primary UoM)
        price_primary = float(combination_info.get("price") or 0.0)
        price_secondary = price_primary * factor

        _logger.info("secondary unit: id=%s name=%s", su.id, secondary_uom_name)
        _logger.info("primary uom name=%s", primary_uom_name)
        _logger.info("factor (secondary -> primary)=%s", factor)
        _logger.info("base price primary(from combination_info['price'])=%s", price_primary)
        _logger.info("computed price_secondary=%s", price_secondary)

        # Inject custom keys
        combination_info.update(
            {
                "sale_secondary_uom_id": su.id,
                "sale_secondary_uom_name": secondary_uom_name,
                "sale_secondary_rounding": su.uom_id.sudo().rounding,
                "sale_secondary_factor": factor,
                "primary_uom_name": primary_uom_name,
                # Keep both for display
                "price_primary_uom": price_primary,      # €/KG
                "price_secondary_uom": price_secondary,  # €/ML
                "wsu_debug_product_id_used": product_sudo.id if product_sudo and product_sudo.exists() else False,
            }
        )

        # IMPORTANT:
        # website_sale JS refreshes ONLY combination_info['price'] into .oe_price
        # So we overwrite it with the secondary-unit price to get live updates.
        combination_info["price"] = price_secondary
        _logger.warning("OVERRIDE combination_info['price'] -> %s (secondary)", price_secondary)

        # Bonus: if list_price exists (discount display), overwrite too
        if "list_price" in combination_info and combination_info.get("list_price"):
            list_price_primary = float(combination_info.get("list_price") or 0.0)
            list_price_secondary = list_price_primary * factor
            combination_info["list_price_primary_uom"] = list_price_primary
            combination_info["list_price_secondary_uom"] = list_price_secondary
            combination_info["list_price"] = list_price_secondary
            _logger.warning("OVERRIDE combination_info['list_price'] -> %s (secondary)", list_price_secondary)

        _logger.info(
            "combination_info injected keys=%s",
            [
                k
                for k in (
                    "has_secondary_uom",
                    "sale_secondary_uom_id",
                    "sale_secondary_uom_name",
                    "sale_secondary_rounding",
                    "sale_secondary_factor",
                    "primary_uom_name",
                    "price_primary_uom",
                    "price_secondary_uom",
                    "price",
                    "list_price",
                    "list_price_primary_uom",
                    "list_price_secondary_uom",
                    "wsu_debug_product_id_used",
                )
                if k in combination_info
            ],
        )
        _logger.info("=== END WSU DEBUG ===")

        return combination_info
