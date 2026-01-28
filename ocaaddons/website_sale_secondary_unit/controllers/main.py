# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

import logging
_logger = logging.getLogger(__name__)


class WebsiteSaleSecondaryUnit(WebsiteSale):

    @staticmethod
    def _to_float(v):
        if v is None:
            return None
        try:
            return float(str(v).replace(",", "."))
        except Exception:
            return None

    @http.route(['/shop/cart/update_json'], type='json', auth="public", website=True)
    def cart_update_json(
        self,
        product_id,
        line_id=None,
        add_qty=None,
        set_qty=None,
        display=True,
        product_custom_attribute_values=None,
        no_variant_attribute_values=None,
        **kw
    ):
        # -------- IN LOGS --------
        _logger.info(
            "WSU cart_update_json IN: product_id=%s line_id=%s add_qty=%s set_qty=%s kw=%s",
            product_id, line_id, add_qty, set_qty, kw
        )

        # sale order avant
        try:
            so_before = request.website.sale_get_order()
            _logger.info(
                "WSU SO(before): id=%s state=%s lines=%s cart_qty=%s",
                so_before.id if so_before else None,
                so_before.state if so_before else None,
                len(so_before.order_line) if so_before else None,
                so_before.cart_quantity if so_before else None,
            )
        except Exception as e:
            _logger.warning("WSU SO(before) read failed: %s", e)

        add_secondary_qty = kw.get("add_secondary_qty")
        secondary_uom_id = kw.get("secondary_uom_id")

        add_qty_f = self._to_float(add_qty)
        set_qty_f = self._to_float(set_qty)
        add_secondary_qty_f = self._to_float(add_secondary_qty)

        # 1) IMPORTANT : si le front n’envoie rien => on force 1
        # (sinon Odoo ajoute 0 et renvoie quantity=0)
        if add_qty_f is None and set_qty_f is None and add_secondary_qty_f is None:
            add_qty_f = 1.0
            _logger.warning("WSU: no qty provided by frontend -> force add_qty=1.0")

        # 2) Conversion secondary -> primary si add_secondary_qty existe
        if add_secondary_qty_f is not None and product_id:
            product = request.env["product.product"].sudo().browse(int(product_id))
            su = product.sale_secondary_uom_id.sudo() if product.exists() else False
            _logger.info(
                "WSU secondary received: add_secondary_qty=%s secondary_uom_id(param)=%s product=%s su=%s factor=%s",
                add_secondary_qty_f, secondary_uom_id,
                product.display_name if product else None,
                su.id if su else None,
                su.factor if su else None,
            )
            if su and su.factor:
                # factor = primaire par secondaire (KG par ML)
                add_qty_f = add_secondary_qty_f * float(su.factor)
                _logger.warning("WSU convert: %s (secondary) -> %s (primary add_qty)", add_secondary_qty_f, add_qty_f)

                # contexte pour d’éventuels hooks sale.order.line
                try:
                    request.update_context(secondary_uom_id=su.id, secondary_uom_qty=add_secondary_qty_f)
                    _logger.info("WSU context injected via request.update_context()")
                except Exception as e:
                    _logger.warning("WSU request.update_context failed: %s", e)

                kw.pop("add_secondary_qty", None)
                kw.pop("secondary_uom_id", None)
            else:
                _logger.warning("WSU: no sale_secondary_uom_id or no factor -> no conversion done")

        _logger.info(
            "WSU CALL super with: product_id=%s line_id=%s add_qty=%s set_qty=%s display=%s",
            product_id, line_id, add_qty_f, set_qty_f, display
        )

        # -------- SUPER --------
        res = super().cart_update_json(
            product_id=int(product_id) if product_id else product_id,
            line_id=line_id,
            add_qty=add_qty_f,
            set_qty=set_qty_f,
            display=display,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_values=no_variant_attribute_values,
            **kw
        )

        # -------- OUT LOGS --------
        _logger.info("WSU cart_update_json OUT: %s", res)

        try:
            so_after = request.website.sale_get_order()
            _logger.info(
                "WSU SO(after): id=%s state=%s lines=%s cart_qty=%s",
                so_after.id if so_after else None,
                so_after.state if so_after else None,
                len(so_after.order_line) if so_after else None,
                so_after.cart_quantity if so_after else None,
            )
            if so_after:
                for l in so_after.order_line:
                    _logger.info(
                        "WSU SO line: id=%s product=%s qty=%s uom=%s price_unit=%s",
                        l.id, l.product_id.display_name, l.product_uom_qty,
                        l.product_uom.name, l.price_unit
                    )
        except Exception as e:
            _logger.warning("WSU SO(after) read failed: %s", e)

        return res
