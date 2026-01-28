# ocaaddons/website_sale_secondary_unit/models/product_template.py
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

        # --- Variant-first: source de vérité = product.product ---
        product = self.env["product.product"].browse(product_id) if product_id else False
        sale_secondary = False
        if product and product.exists():
            sale_secondary = product.sale_secondary_uom_id
        # fallback template si produit simple (ou si pas de product_id)
        if not sale_secondary:
            sale_secondary = self.sale_secondary_uom_id

        has_secondary = bool(sale_secondary)
        combination_info.update({"has_secondary_uom": has_secondary})

        if has_secondary:
            # facteur = kg par ML (dans ton cas), stocké sur product.secondary.unit.factor
            factor = sale_secondary.factor or 0.0
            primary_uom_name = (product.uom_id.name if product else self.uom_id.name)

            # combination_info['price'] = prix unitaire Odoo (donc ici €/KG si ta UoM primaire = KG)
            price_primary = combination_info.get("price", 0.0) or 0.0
            price_secondary = price_primary * factor

            combination_info.update(
                {
                    "sale_secondary_uom_id": sale_secondary.id,
                    "sale_secondary_uom_name": sale_secondary.uom_id.name,  # ex: ML
                    "sale_secondary_name": sale_secondary.name,  # ex: ML ou "ml" interne
                    "sale_secondary_rounding": sale_secondary.uom_id.rounding,
                    "sale_secondary_factor": factor,
                    "primary_uom_name": primary_uom_name,  # ex: KG
                    "price_primary_uom": price_primary,  # €/KG
                    "price_secondary_uom": price_secondary,  # €/ML
                }
            )
        return combination_info
