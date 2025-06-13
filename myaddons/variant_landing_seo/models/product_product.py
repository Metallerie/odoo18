from odoo import models, fields, api
import re

def slugify(text):
    text = re.sub(r'\W+', '-', text.lower()).strip('-')
    return text

class ProductProduct(models.Model):
    _inherit = 'product.product'

    variant_slug = fields.Char(string="Slug URL", compute="_compute_variant_slug", store=True)

    @api.depends('product_tmpl_id.name', 'product_template_attribute_value_ids.attribute_value_id.name')
    def _compute_variant_slug(self):
        for variant in self:
            parts = [slugify(variant.product_tmpl_id.name)]
            values = variant.attribute_value_ids.sorted(key=lambda v: v.attribute_id.name)
            parts += [slugify(v.name) for v in values]
            variant.variant_slug = '-'.join(parts)
