from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_composed_product = fields.Boolean(
        string='Produit composé'
    )

    purchase_sale_coef = fields.Float(
        string='Coefficient prix',
        default=1.0
    )

    composition_line_ids = fields.One2many(
        'product.composition.line',
        'product_tmpl_id',
        string='Composants'
    )
