from odoo import models, fields


class ProductCompositionLine(models.Model):
    _name = 'product.composition.line'
    _description = 'Product Composition Line'
    _order = 'sequence, id'

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Produit parent',
        required=True,
        ondelete='cascade'
    )

    component_product_id = fields.Many2one(
        'product.product',
        string='Produit composant',
        required=True,
        domain="[('categ_id', '=', 10)]"
    )

    quantity_formula = fields.Char(
        string='Formule de quantité',
        help="Ex: poids, surface, perimetre * epaisseur"
    )

    attribute_id = fields.Many2one(
        'product.attribute',
        string='Attribut source'
    )

    attribute_value_id = fields.Many2one(
        'product.attribute.value',
        string='Valeur source',
        domain="[('attribute_id', '=', attribute_id)]"
    )

    sequence = fields.Integer(
        string='Ordre',
        default=10
    )

    active = fields.Boolean(
        default=True
    )
