
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"
    
    #Précision personnalisée pour l'unité de mesure de cette variante de produit
    uom_precision = fields.Integer(
         related="product_variant_ids.uom_precision", readonly=False,
         string="Précision UoM",
         help="Précision personnalisée pour l'unité de mesure de cette variante de produit. Laisser vide pour utiliser la précision par défaut.",
    )

    # Define all the related fields in product.template with 'readonly=False'
    # to be able to modify the values from product.template.
    dimensional_uom_id = fields.Many2one(
        "uom.uom",
        "Dimensional UoM",
        related="product_variant_ids.dimensional_uom_id",
        help="UoM for length, height, width",
        readonly=False,
    )
    product_length = fields.Float(
        related="product_variant_ids.product_length", readonly=False,
        digits=(16, 6)
    )
    product_height = fields.Float(
        related="product_variant_ids.product_height", readonly=False, digits=(16, 6)
    )
    product_width = fields.Float(
        related="product_variant_ids.product_width", readonly=False, digits=(16, 6)
    )
    volume = fields.Float(
        compute="_compute_volume",
        readonly=False,
        store=True,
        digits=(16, 6)
    )
    product_thickness = fields.Float(
        related="product_variant_ids.product_thickness", string="Thickness ",readonly=False, digits=(16, 6)
    )
    product_diameter = fields.Float(
        related="product_variant_ids.product_diameter",string="Diametre", readonly=False, digits=(16, 6)
    )
    uom_po_id = fields.Many2one(
        'uom.uom', 'Purchase Unit',
        default=_get_default_uom_id, required=True,
        domain=[],
        help="Default unit of measure used for purchase orders. It is not restricted to the same category as the sales unit."
    )

    @api.onchange('uom_id', 'uom_po_id')
    def _onchange_uom_po_id(self):
        if self.uom_id and self.uom_po_id and self.uom_id.category_id != self.uom_po_id.category_id:
        return {
            'warning': {
                'title': "Attention",
                'message': "L'unité d'achat (%s) et l'unité de vente (%s) appartiennent à des catégories différentes. Assurez-vous que cela est intentionnel." % (self.uom_po_id.name, self.uom_id.name),
            }
        }

    @api.constrains('uom_id', 'uom_po_id')
    def _check_uom_category(self):
        # ❌ on neutralise la contrainte Odoo qui bloque les catégories différentes
        pass
    

    @api.model
    def _calc_volume(self, product_length, product_height, product_width, uom_id):
        volume = 0
        if product_length and product_height and product_width and uom_id:
            length_m = self.convert_to_meters(product_length, uom_id)
            height_m = self.convert_to_meters(product_height, uom_id)
            width_m = self.convert_to_meters(product_width, uom_id)
            volume = length_m * height_m * width_m

        return volume

    @api.depends(
        "product_length", "product_height", "product_width", "dimensional_uom_id"
    )
    def _compute_volume(self):
        for template in self:
            template.volume = template._calc_volume(
                template.product_length,
                template.product_height,
                template.product_width,
                template.dimensional_uom_id,
            )

    def convert_to_meters(self, measure, dimensional_uom):
        uom_meters = self.env.ref("uom.product_uom_meter")

        return dimensional_uom._compute_quantity(
            qty=measure,
            to_unit=uom_meters,
            round=False,
        )

    def _prepare_variant_values(self, combination):
        """
        As variant is created inside template create() method and as
        template fields values are flushed after _create_variant_ids(),
        we catch the variant values preparation to update them
        """
        res = super()._prepare_variant_values(combination)
        if self.product_length:
            res.update({"product_length": self.product_length})
        if self.product_height:
            res.update({"product_height": self.product_height})
        if self.product_width:
            res.update({"product_width": self.product_width})
        return res
        
    
