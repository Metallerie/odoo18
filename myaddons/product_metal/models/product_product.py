from odoo import api, fields, models

class ProductProduct(models.Model):
    _inherit = "product.product"
    
    # Précision personnalisée pour l'unité de mesure de cette variante de produit
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
    
    @api.depends("product_length", "product_height", "product_width", "dimensional_uom_id")
    def _compute_volume(self):
        template_obj = self.env["product.template"]
        for product in self:
            product.volume = template_obj._calc_volume(
                product.product_length,
                product.product_height,
                product.product_width,
                product.dimensional_uom_id,
            )

    @api.onchange('uom_po_id')
    def _onchange_uom(self):
        if self.uom_id and self.uom_po_id and self.uom_id.category_id != self.uom_po_id.category_id:
            _logger.warning(f"[UOM INFO] Vente en {self.uom_id.name}, achat en {self.uom_po_id.name} pour {self.display_name}")

    def _get_dimension_uom_domain(self):
        """
        Retourne un domaine pour filtrer les unités de mesure utilisées pour les dimensions
        (longueur, largeur, hauteur).
        """
        return [("category_id.name", "=", "Length")]
