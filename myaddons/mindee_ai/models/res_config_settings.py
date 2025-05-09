from odoo import api, fields, models, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mindee_api_key = fields.Char(string="Clé API Mindee")

    @api.model
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('mindee_ai.mindee_api_key', self.mindee_api_key)

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res['mindee_api_key'] = self.env['ir.config_parameter'].sudo().get_param('mindee_ai.mindee_api_key', default='')
        return res
