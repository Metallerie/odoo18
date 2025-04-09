from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    whatsapp_phone = fields.Char(string="Numéro WhatsApp")
