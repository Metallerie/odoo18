# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

import logging
_logger = logging.getLogger(__name__)


class WebsiteSaleSecondaryUnit(WebsiteSale):
    """
    Odoo 18:
    - le site appelle /shop/cart/update_json
    - si ton template envoie add_secondary_qty (ex: ML), Odoo ne sait pas quoi en faire
    => on convertit en add_qty (UoM primaire du produit, ex: KG) puis on appelle super()
    """

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
        # --- LOGS INPUT ---
        _logger.info("WSU cart_update_json IN: product_id=%s line_id=%s add_qty=%s set_qty=%s kw=%s",
                     product_id, line_id, add_qty, set_qty, kw)

        add_secondary_qty = kw.get("add_secondary_qty")
        secondary_uom_id = kw.get("secondary_uom_id")

        # Normalisation float
        def _to_float(v):
            if v is None:
                return None
            try:
                return float(str(v).replace(",", "."))
            except Exception:
                return None

        add_secondary_qty_f = _to_float(add_secondary_qty)
        add_qty_f = _to_float(add_qty)
        set_qty_f = _to_float(set_qty)

        # Conversion secondary -> primary si on a une qty secondaire
        if add_secondary_qty_f is not None and product_id:
            product = request.env["product.product"].sudo().browse(int(product_id))
            su = product.sale_secondary_uom_id.sudo() if product.exists() else False

            _logger.info(
                "WSU secondary received: add_secondary_qty=%s secondary_uom_id(param)=%s product=%s su=%s factor=%s",
                add_secondary_qty_f, secondary_uom_id, product.display_name if product else None,
                su.id if su else None, su.factor if su else None
            )

            if su and su.factor:
                # chez toi: factor = KG par ML (secondary -> primary)
                primary_qty = add_secondary_qty_f * float(su.factor)
                add_qty_f = primary_qty  # on force add_qty (KG)
                # on laisse set_qty vide (sinon Odoo interprète différemment)
                _logger.warning("WSU convert: %s (secondary) -> %s (primary add_qty)", add_secondary_qty_f, add_qty_f)

                # mettre aussi en contexte pour le sale.order.line si besoin
                try:
                    request.update_context(
                        secondary_uom_id=su.id,
                        secondary_uom_qty=add_secondary_qty_f,
                    )
                    _logger.info("WSU context injected via request.update_context()")
                except Exception as e:
                    _logger.warning("WSU request.update_context failed: %s", e)

                # IMPORTANT: ne pas laisser le kw add_secondary_qty perturber d'autres couches
                kw.pop("add_secondary_qty", None)
                kw.pop("secondary_uom_id", None)
            else:
                _logger.warning("WSU: no sale_secondary_uom_id or no factor -> no conversion done")

        # --- CALL SUPER ---
        res = super().cart_update_json(
            product_id=int(product_id) if product_id else product_id,
            line_id=line_id,
            add_qty=add_qty_f if add_qty_f is not None else add_qty,
            set_qty=set_qty_f if set_qty_f is not None else set_qty,
            display=display,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_values=no_variant_attribute_values,
            **kw
        )

        # --- LOGS OUTPUT ---
        _logger.info("WSU cart_update_json OUT: %s", res)
        return res
