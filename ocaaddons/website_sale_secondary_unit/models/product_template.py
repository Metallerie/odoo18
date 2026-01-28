# -*- coding: utf-8 -*-
# ocaaddons/website_sale_secondary_unit/models/product_template.py
#
# DEBUG-heavy version (logs en console Odoo)
#
import logging
import json

from odoo import fields, models

_logger = logging.getLogger(__name__)


def _j(obj):
    """json pretty (safe)"""
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)


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
        # --- SUPER ---
        combination_info = super()._get_combination_info(
            combination=combination,
            product_id=product_id,
            add_qty=add_qty,
            parent_combination=parent_combination,
            only_template=only_template,
        )

        # --- DEBUG HEADER ---
        try:
            tmpl = self.sudo()
            _logger.info("=== WSU DEBUG (product.template._get_combination_info) ===")
            _logger.info(
                "tmpl=%s (%s) product_id(arg)=%s add_qty=%s only_template=%s",
                tmpl.display_name,
                tmpl.id,
                product_id,
                add_qty,
                only_template,
            )
            _logger.info("combination(arg)=%s parent_combination=%s", bool(combination), bool(parent_combination))

            # IMPORTANT: in website, product_id peut être False au 1er rendu
            product = self.env["product.product"].browse(int(product_id)) if product_id else self.env["product.product"]
            product_sudo = product.sudo() if product_id else False

            if product_sudo and product_sudo.exists():
                _logger.info("picked product=%s (%s)", product_sudo.display_name, product_sudo.id)
            else:
                _logger.info("picked product=<none> (product_id was False or invalid)")

            # --- BASE PRICE INFO FROM SUPER ---
            base_price = float(combination_info.get("price") or 0.0)
            price_extra = float(combination_info.get("price_extra") or 0.0)
            list_price = float(combination_info.get("list_price") or 0.0) if "list_price" in combination_info else None

            _logger.info("base price (primary, combination_info['price'])=%s", base_price)
            _logger.info("price_extra=%s", price_extra)
            if list_price is not None:
                _logger.info("list_price=%s", list_price)

            # log un peu plus large (sans spammer comme un porc)
            keys_of_interest = [
                "price",
                "list_price",
                "price_extra",
                "has_discounted_price",
                "discounted_price",
                "prevent_zero_price_sale",
                "product_id",
                "product_template_id",
                "display_name",
                "variant_name",
                "currency_id",
                "currency_symbol",
                "is_combination_possible",
            ]
            snap = {k: combination_info.get(k) for k in keys_of_interest if k in combination_info}
            _logger.info("combination_info snapshot=%s", _j(snap))

            # --- PICK SECONDARY UOM (variant-first, fallback template) ---
            sale_secondary = False
            var_su = False
            tmpl_su = False

            if product_sudo and product_sudo.exists():
                var_su = product_sudo.sale_secondary_uom_id
            tmpl_su = tmpl.sale_secondary_uom_id

            _logger.info("variant sale_secondary_uom_id=%s", var_su.ids if var_su else [])
            _logger.info("template sale_secondary_uom_id=%s", tmpl_su.ids if tmpl_su else [])

            sale_secondary = var_su or tmpl_su
            has_secondary = bool(sale_secondary)

            # on injecte toujours le bool, même False (pratique côté QWeb/JS)
            combination_info.update(
                {
                    "has_secondary_uom": has_secondary,
                    "wsu_debug_product_id_used": product_sudo.id if (product_sudo and product_sudo.exists()) else False,
                }
            )
            _logger.info("HAS secondary uom=%s", has_secondary)

            if not has_secondary:
                _logger.warning("NO secondary UOM FOUND -> nothing injected")
                _logger.info("=== END WSU DEBUG ===")
                return combination_info

            # --- COMPUTE SECONDARY PRICE + META ---
            su = sale_secondary.sudo()

            secondary_uom_name = su.uom_id.sudo().name
            primary_uom_name = (
                product_sudo.uom_id.sudo().name if (product_sudo and product_sudo.exists()) else tmpl.uom_id.sudo().name
            )

            factor = float(su.factor or 0.0)  # (chez toi: kg par ML)
            price_primary = base_price
            price_secondary = price_primary * factor

            _logger.info("secondary unit: id=%s name=%s", su.id, secondary_uom_name)
            _logger.info("primary uom name=%s", primary_uom_name)
            _logger.info("factor (secondary -> primary)=%s", factor)
            _logger.info("price_secondary=%s", price_secondary)

            # injection finale
            injected = {
                "sale_secondary_uom_id": su.id,
                "sale_secondary_uom_name": secondary_uom_name,
                "sale_secondary_rounding": su.uom_id.sudo().rounding,
                "sale_secondary_factor": factor,
                "primary_uom_name": primary_uom_name,
                "price_primary_uom": price_primary,      # €/UoM primaire (souvent KG)
                "price_secondary_uom": price_secondary,  # €/UoM secondaire (souvent ML)
            }
            combination_info.update(injected)

            _logger.info("combination_info injected keys=%s", list(injected.keys()))
            _logger.info("=== END WSU DEBUG ===")
            return combination_info

        except Exception as e:
            # si jamais ton site crashe, on veut au moins la trace + retour super()
            _logger.exception("WSU ERROR in _get_combination_info: %s", e)
            return combination_info
