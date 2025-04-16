# models/blog_post.py
from odoo import models

class BlogPost(models.Model):
    _inherit = ['blog.post', 'link_checker.seo.mixin']
