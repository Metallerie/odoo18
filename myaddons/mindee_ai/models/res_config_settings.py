from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mindee_backend = fields.Selection([
        ('doctr', 'docTR (local)'),
        ('mindee_v2', 'Mindee v2 (SaaS)'),
    ], string="Moteur OCR", config_parameter='mindee_ai.backend', default='doctr')

    mindee_doctr_url = fields.Char(
        string="docTR URL",
        config_parameter='mindee_ai.doctr_url',
        default='http://127.0.0.1:1998/ocr'
    )

    mindee_api_key = fields.Char(
        string="Mindee API Key",
        config_parameter='mindee_ai.mindee_api_key'
    )
    mindee_model_id = fields.Char(
        string="Mindee Model ID",
        config_parameter='mindee_ai.model_id'
    )
