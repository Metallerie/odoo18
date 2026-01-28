# ocaaddons/website_sale_secondary_unit/controllers/main.py
from odoo import http
from odoo.http import request
from odoo.tools.float_utils import float_round
from odoo.addons.website_sale.controllers.main import WebsiteSale


def _parse_float_fr(v):
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


class WebsiteSaleSecondaryUnit(WebsiteSale):

    def _get_forced_secondary_uom(self, product):
        # ✅ Unité unique = unité secondaire de vente de la variante
        su = product.sale_secondary_uom_id
        return su

    @http.route()
    def cart_update(self, product_id, add_qty=1, set_qty=0, **kw):
        product = request.env["product.product"].browse(int(product_id))
        su = self._get_forced_secondary_uom(product)

        # Si pas d'unité secondaire -> comportement standard
        if not su:
            return super().cart_update(product_id, add_qty=add_qty, set_qty=set_qty, **kw)

        # Quantité saisie = secondaire
        sec_qty = _parse_float_fr(kw.get("add_secondary_qty") or kw.get("set_secondary_qty") or add_qty)

        # Conversion serveur -> primaire (KG)
        primary_qty = float_round(
            sec_qty * (su.factor or 1.0),
            precision_rounding=(product.uom_id.rounding or 0.01),
        )

        # Stoker uom secondaire en session (pour que la ligne reste cohérente)
        request.session["secondary_uom_id"] = su.id

        # On pousse aussi la qty secondaire via context pour la ligne
        return super(WebsiteSaleSecondaryUnit, self.with_context(
            secondary_uom_id=su.id,
            secondary_uom_qty=sec_qty,
        )).cart_update(product_id, add_qty=primary_qty, set_qty=0, **kw)

    @http.route()
    def cart_update_json(self, product_id, line_id=None, add_qty=None, set_qty=None, display=True, **kw):
        product = request.env["product.product"].browse(int(product_id))
        su = self._get_forced_secondary_uom(product)

        if not su:
            return super().cart_update_json(
                product_id, line_id=line_id, add_qty=add_qty, set_qty=set_qty, display=display, **kw
            )

        sec_qty = _parse_float_fr(kw.get("set_secondary_qty") or kw.get("add_secondary_qty") or set_qty or add_qty)

        primary_qty = float_round(
            sec_qty * (su.factor or 1.0),
            precision_rounding=(product.uom_id.rounding or 0.01),
        )

        request.session["secondary_uom_id"] = su.id

        # On force set_qty en primaire (KG)
        return super(WebsiteSaleSecondaryUnit, self.with_context(
            secondary_uom_id=su.id,
            secondary_uom_qty=sec_qty,
        )).cart_update_json(
            product_id,
            line_id=line_id,
            add_qty=None,
            set_qty=primary_qty,
            display=display,
            **kw,
        )
