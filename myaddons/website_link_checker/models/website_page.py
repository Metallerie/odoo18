# models/website_page.py
from odoo import models, fields

class WebsitePage(models.Model):
    _inherit = 'website.page'

    exclude_from_sitemap = fields.Boolean(string="Exclure du sitemap")
