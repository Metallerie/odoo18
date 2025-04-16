from odoo import models
from .seo_mixin import SEOVisibilityMixin

class WebsitePage(models.Model):
    _inherit = ['website.page', 'link_checker.seo.mixin']
