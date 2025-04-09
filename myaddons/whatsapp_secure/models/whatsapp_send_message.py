from odoo import models, fields

class WhatsAppSendMessage(models.TransientModel):
    _name = 'whatsapp.send.message'
    _description = 'Envoyer un message WhatsApp'

    user_id = fields.Many2one('res.users', string="Utilisateur", default=lambda self: self.env.user, readonly=True)
    mobile = fields.Char(string="Numéro")
    message = fields.Text(string="Message")

    def action_send_message(self):
        # Logique ou redirection vers le contrôleur si tu veux
        return {'type': 'ir.actions.act_window_close'}
