
from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"
    
    #Précision personnalisée pour l'unité de mesure de cette variante de produit
    uom_precision = fields.Integer(
         string="Précision UoM",
         help="Précision personnalisée pour l'unité de mesure de cette variante de produit. Laisser vide pour utiliser la précision par défaut.",
    )
    product_length = fields.Float("length", digits=(16, 6))
    product_height = fields.Float("height", digits=(16, 6))
    product_width = fields.Float("width", digits=(16, 6))
    product_thickness = fields.Float("thickness", digits=(16, 6))
    product_diameter = fields.Float("diameter", digits=(16, 6))
    dimensional_uom_id = fields.Many2one(
        "uom.uom",
        "Dimensional UoM",
        domain=lambda self: self._get_dimension_uom_domain(),
        help="UoM for length, height, width",
        default=lambda self: self.env.ref("uom.product_uom_meter"),
    )
    volume = fields.Float(
        compute="_compute_volume",
        readonly=False,
        store=True,
    )
    

    @api.depends(
        "product_length", "product_height", "product_width", "dimensional_uom_id"
    )
    def _compute_volume(self):
        template_obj = self.env["product.template"]
        for product in self:
            product.volume = template_obj._calc_volume(
                product.product_length,
                product.product_height,
                product.product_width,
                product.dimensional_uom_id,
            )

    @api.model
    def _get_dimension_uom_domain(self):
        return [("category_id", "=", self.env.ref("uom.uom_categ_length").id)]
        
    @api.constrains('uom_id', 'uom_po_id')
    def _check_uom_category(self):
        # 🔓 On désactive volontairement la contrainte standard Odoo
        # Cela permet d'utiliser des unités dans des catégories différentes (ex: mètre et kg)
        pass
