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
 
  
    
    
       

   
    
