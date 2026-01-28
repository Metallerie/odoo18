# ocaaddons/website_sale_secondary_unit/models/sale_order_line.py
from odoo import api, models
from odoo.tools.float_utils import float_round


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _secondary_factor(self, secondary_uom, uom):
        # uom.factor peut être non-1, mais chez toi KG => souvent 1
        return (secondary_uom.factor or 0.0) * (uom.factor or 1.0)

    @api.model_create_multi
    def create(self, vals_list):
        SecondaryUom = self.env["product.secondary.unit"]
        Uom = self.env["uom.uom"]

        for vals in vals_list:
            secondary_uom = SecondaryUom.browse(vals.get("secondary_uom_id") or False)
            uom = Uom.browse(vals.get("product_uom") or False)

            if not secondary_uom:
                continue

            factor = self._secondary_factor(secondary_uom, uom)

            # ✅ Priorité: si le website fournit secondary_uom_qty, on calcule product_uom_qty (KG)
            if "secondary_uom_qty" in vals and vals["secondary_uom_qty"] is not None:
                qty_secondary = float(vals["secondary_uom_qty"])
                vals["product_uom_qty"] = float_round(
                    qty_secondary * (factor or 1.0),
                    precision_rounding=(uom.rounding or 0.01),
                )
            else:
                # fallback historique: calculer secondary depuis product_uom_qty
                vals["secondary_uom_qty"] = float_round(
                    float(vals.get("product_uom_qty", 0.0)) / (factor or 1.0),
                    precision_rounding=secondary_uom.uom_id.rounding,
                )

        return super().create(vals_list)

    def write(self, vals):
        SecondaryUom = self.env["product.secondary.unit"]
        Uom = self.env["uom.uom"]

        for line in self:
            secondary_uom = (
                ("secondary_uom_id" in vals and SecondaryUom.browse(vals["secondary_uom_id"]))
                or line.secondary_uom_id
            )
            uom = (("product_uom" in vals and Uom.browse(vals["product_uom"])) or line.product_uom)

            if not secondary_uom:
                continue

            factor = self._secondary_factor(secondary_uom, uom)

            # ✅ si on change la qty secondaire, on recalcule la primaire (KG)
            if "secondary_uom_qty" in vals and vals["secondary_uom_qty"] is not None:
                qty_secondary = float(vals["secondary_uom_qty"])
                vals["product_uom_qty"] = float_round(
                    qty_secondary * (factor or 1.0),
                    precision_rounding=(uom.rounding or 0.01),
                )
                continue

            # fallback historique: si on change la primaire, on recalcule la secondaire
            if "product_uom_qty" in vals and secondary_uom:
                vals["secondary_uom_qty"] = float_round(
                    float(vals["product_uom_qty"]) / (factor or 1.0),
                    precision_rounding=secondary_uom.uom_id.rounding,
                )

        return super().write(vals)
