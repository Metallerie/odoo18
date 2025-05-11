from odoo import api, fields, models, tools


class ProductTemplate(models.Model):
    _inherit = "product.template"

    product_kg_ml = fields.Float(
        related="product_variant_ids.product_kg_ml",
        string="Poids (kg) par mètre linéaire",
        digits='Product Unit of Measure'
        readonly=False,

    )

    # Précision personnalisée pour l'unité de mesure de cette variante de produit
    uom_precision = fields.Integer(
        related="product_variant_ids.uom_precision",
        readonly=False,
        string="Précision UoM",
        help="Précision personnalisée pour l'unité de mesure de cette variante de produit. Laisser vide pour utiliser la précision par défaut.",
    )


    product_length = fields.Float(
        related="product_variant_ids.product_length",
        readonly=False,
        digits=(16, 6),
    )
    product_height = fields.Float(
        related="product_variant_ids.product_height",
        readonly=False,
        digits=(16, 6),
    )
    product_width = fields.Float(
        related="product_variant_ids.product_width",
        readonly=False,
        digits=(16, 6),
    )
    volume = fields.Float(
        compute="_compute_volume",
        readonly=False,
        store=True,
        digits=(16, 6),
    )
    product_thickness = fields.Float(
        related="product_variant_ids.product_thickness",
        string="Épaisseur",
        readonly=False,
        digits=(16, 6),
    )
    product_diameter = fields.Float(
        related="product_variant_ids.product_diameter",
        string="Diamètre",
        readonly=False,
        digits=(16, 6),
    )
  
 
