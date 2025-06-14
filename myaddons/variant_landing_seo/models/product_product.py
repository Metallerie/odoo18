from odoo import models, fields, api
import re

def slugify(text):
    text = re.sub(r'\W+', '-', text.lower()).strip('-')
    return text

class ProductProduct(models.Model):
    _inherit = 'product.product'

    variant_slug = fields.Char(string="Slug URL", compute="_compute_variant_slug", store=True)

    @api.depends('product_template_attribute_value_ids.name', 'product_template_attribute_value_ids.attribute_id.name', 'product_tmpl_id.name')
    def _compute_variant_slug(self):
        for variant in self:
            parts = [variant.product_tmpl_id.name]
            for ptav in variant.product_template_attribute_value_ids:
                parts.append(ptav.name.replace(" ", "-"))
            slug = slugify("-".join(parts)) if parts else False
            variant.variant_slug = slug
