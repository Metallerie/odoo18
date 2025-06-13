from odoo import models, fields, api
import re

def slugify(text):
    text = re.sub(r'\W+', '-', text.lower()).strip('-')
    return text

class ProductProduct(models.Model):
    _inherit = 'product.product'

    variant_slug = fields.Char(string="Slug URL", compute="_compute_variant_slug", store=True)

    @api.depends('product_tmpl_id.name', 'product_template_attribute_value_ids.name')
    def _compute_variant_slug(self):
        for variant in self:
            tmpl_name = variant.product_tmpl_id.name or ''
            parts = [slugify(tmpl_name)]

            values = variant.product_template_attribute_value_ids.sorted(
                key=lambda val: val.attribute_id.name
            )
            parts += [slugify(val.name) for val in values]

            variant.variant_slug = '-'.join(parts)
