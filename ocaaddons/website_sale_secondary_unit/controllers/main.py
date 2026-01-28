# -*- coding: utf-8 -*-
# ocaaddons/website_sale_secondary_unit/controllers/main.py

from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

import logging
_logger = logging.getLogger(__name__)


class WebsiteSaleSecondaryUnit(WebsiteSale):

    @http.route(
        ["/shop/cart/update_json"],
        type="json",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=False,
    )
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
        """
        Odoo 18: controller object has NO with_context()
        -> we must pass context through request.env.context.
        """

        ctx = dict(request.env.context)

        # OCA module uses "add_secondary_qty" coming from template input name="add_secondary_qty"
        add_secondary_qty = kw.get("add_secondary_qty")
        if add_secondary_qty is not None:
            try:
                add_secondary_qty = float(add_secondary_qty)
            except Exception:
                add_secondary_qty = None

        if add_secondary_qty:
            ctx["add_secondary_qty"] = add_secondary_qty
            _logger.info("WSU controller: add_secondary_qty=%s -> injected into context", add_secondary_qty)

        # If they also send secondary_uom_id
        secondary_uom_id = kw.get("secondary_uom_id")
        if secondary_uom_id:
            try:
                ctx["secondary_uom_id"] = int(secondary_uom_id)
            except Exception:
                pass

        # Call super in a request env with overridden context
        # IMPORTANT: do NOT use self.with_context() here
        return super(WebsiteSaleSecondaryUnit, self).cart_update_json(
            product_id=product_id,
            line_id=line_id,
            add_qty=add_qty,
            set_qty=set_qty,
            display=display,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_values=no_variant_attribute_values,
            **kw,
            **{"context": ctx},  # <-- DOES NOT work in Odoo; keep below alternative
        )
