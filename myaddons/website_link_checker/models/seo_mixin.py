# models/seo_mixin.py
from odoo import models, fields

class SEOVisibilityMixin(models.AbstractModel):
    _name = 'link_checker.seo.mixin'
    _description = 'Mixin pour le contrôle SEO'

    exclude_from_sitemap = fields.Boolean(string="Exclure du sitemap")
    noindex = fields.Boolean(string="Ajouter balise noindex")
