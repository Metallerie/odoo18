# -*- coding: utf-8 -*-
# ocaaddons/website_sale_secondary_unit/models/product_template.py
#
# Debug version with explicit console logs.
# Goal: always compute secondary UoM from the *variant* when possible, including
# the first render where product_id can be False.
#
# Copyright 2019 Tecnativa - Sergio Teruel
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    allow_uom_sell = fields.Boolean(
        string="Allow to sell in unit of measure",
        default=True,
    )

    def _wsu_pick_product(self, product_id=False, combination=False):
        """Pick the best product.product to use for website computation."""
        self.ensure_one()

        Product = self.env["product.product"]

        # 1) Explicit product_id passed by website (AJAX /get_combination_info)
        if product_id:
            prod = Product.browse(int(product_id)).exists()
            if prod:
                return prod

        # 2) Sometimes combination is passed (variant attributes). Try to resolve.
        #    (Keep safe: different Odoo versions differ here.)
        try:
            if combination and isinstance(combination, (list, tuple)) and combination:
                # In some flows, combination can be a list of ptav ids; Odoo core will
                # resolve the variant later anyway. We fall back to default variant.
                pass
        except Exception:
            pass

        # 3) First render: website calls _get_combination_info with product_id=False.
        #    Use the template's "default" variant.
        if self.product_variant_id:
            return self.product_variant_id

        # 4) Last resort (shouldn't happen)
        return Product

    def _wsu_get_sale_secondary(self, product):
        """Variant-first, then template fallback. Returns product.secondary.unit record or False."""
        self.ensure_one()

        sale_secondary = False

        # Variant-first (what you want for website)
        if product and getattr(product, "id", False):
            try:
                sale_secondary = product.sudo().sale_secondary_uom_id
            except Exception as e:
                _logger.warning("WSU: cannot read variant sale_secondary_uom_id (%s)", e)

        # Fallback on template
        if not sale_secondary:
            try:
                sale_secondary = self.sudo().sale_secondary_uom_id
            except Exception as e:
                _logger.warning("WSU: cannot read template sale_secondary_uom_id (%s)", e)

        return sale_secondary or False

    def _get_combination_info(
        self,
        combination=False,
        product_id=False,
        add_qty=1,
        parent_combination=False,
        only_template=False,
    ):
        self.ensure_one()

        combination_info = super()._get_combination_info(
            combination=combination,
            product_id=product_id,
            add_qty=add_qty,
            parent_combination=parent_combination,
            only_template=only_template,
        )

        # -------------------------
        # DEBUG HEADER
        # -------------------------
        _logger.info("=== WSU DEBUG (product.template._get_combination_info) ===")
        _logger.info("tmpl=%s (%s) product_id(arg)=%s add_qty=%s only_template=%s",
                     self.display_name, self.id, product_id, add_qty, only_template)

        # Pick a product for computation (IMPORTANT for first render)
        product = self._wsu_pick_product(product_id=product_id, combination=combination)
        _logger.info("picked product=%s", getattr(product, "id", False) and f"{product.display_name} ({product.id})" or "None/empty")

        # Base price from core
        base_price_primary = float(combination_info.get("price") or 0.0)
        _logger.info("base price (primary, from combination_info['price'])=%s", base_price_primary)

        # Identify secondary unit
        sale_secondary = self._wsu_get_sale_secondary(product)
        has_secondary = bool(sale_secondary)
        _logger.info("variant sale_secondary_uom_id=%s",
                     getattr(product.sudo(), "sale_secondary_uom_id", self.env["product.secondary.unit"]).ids if getattr(product, "id", False) else "n/a")
        _logger.info("template sale_secondary_uom_id=%s", self.sudo().sale_secondary_uom_id.ids)
        _logger.info("HAS secondary uom=%s", has_secondary)

        # Always expose the flag (templates use it)
        combination_info.update({"has_secondary_uom": has_secondary})

        if not has_secondary:
            _logger.warning("WSU: NO secondary UOM -> nothing injected")
            _logger.info("=== END WSU DEBUG ===")
            return combination_info

        su = sale_secondary.sudo()

        # Names should be readable by public user => sudo
        try:
            secondary_uom_name = su.uom_id.sudo().name  # ex: ML
        except Exception:
            secondary_uom_name = su.display_name
        try:
            primary_uom_name = (product.sudo().uom_id.sudo().name if getattr(product, "id", False) else self.sudo().uom_id.sudo().name)  # ex: KG
        except Exception:
            primary_uom_name = "UoM"

        # Factor: you said "kg par ML" in your case.
        # On OCA product.secondary.unit, common fields are:
        # - factor (float)
        # - uom_id (Many2one to uom.uom)
        factor = float(getattr(su, "factor", 0.0) or 0.0)

        # Compute price per secondary
        price_primary = base_price_primary
        price_secondary = price_primary * factor

        _logger.info("secondary unit: id=%s name=%s", su.id, secondary_uom_name)
        _logger.info("primary uom name=%s", primary_uom_name)
        _logger.info("factor (secondary -> primary)=%s", factor)
        _logger.info("price_secondary=%s", price_secondary)

        # rounding for the secondary uom (uom.uom rounding)
        rounding = 0.01
        try:
            rounding = float(su.uom_id.sudo().rounding or 0.01)
        except Exception:
            pass

        # Inject everything your templates need
        combination_info.update(
            {
                "sale_secondary_uom_id": su.id,
                "sale_secondary_uom_name": secondary_uom_name,
                "sale_secondary_rounding": rounding,
                "sale_secondary_factor": factor,
                "primary_uom_name": primary_uom_name,
                "price_primary_uom": price_primary,      # €/KG (primary)
                "price_secondary_uom": price_secondary,  # €/ML (secondary)
                # extra debug helpers (optional)
                "wsu_debug_product_id_used": getattr(product, "id", False) or False,
            }
        )

        _logger.info("combination_info injected keys=%s",
                     [k for k in combination_info.keys() if k.startswith("sale_secondary_") or k.startswith("price_") or k in ("has_secondary_uom", "primary_uom_name", "wsu_debug_product_id_used")])
        _logger.info("=== END WSU DEBUG ===")

        return combination_info
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
