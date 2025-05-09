# -*- coding: utf-8 -*-
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mindee_api_key = fields.Char(
        string="Clé API Mindee",
        config_parameter='mindee_ai.api_key'
    )
