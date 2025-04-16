# models/product_template.py
from odoo import models

class ProductTemplate(models.Model):
    _inherit = ['product.template', 'link_checker.seo.mixin']
