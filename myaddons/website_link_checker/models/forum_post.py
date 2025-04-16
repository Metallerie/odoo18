# models/forum_post.py
from odoo import models

class ForumPost(models.Model):
    _inherit = ['forum.post', 'link_checker.seo.mixin']
