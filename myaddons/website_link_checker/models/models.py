# models/website.py
from odoo import models, fields

class Website(models.Model):
    _inherit = 'website'

    link_checker_user_id = fields.Many2one(
        'res.users',
        string="Destinataire des rapports de liens cassés"
    )
