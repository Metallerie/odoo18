from odoo import http
from odoo.http import request
from urllib.parse import quote

class WhatsAppRedirect(http.Controller):

    @http.route('/whatsapp/send', type='http', auth='public', website=True)
    def whatsapp_redirect(self, phone=None, text=None, **kwargs):
        company = request.env.company
        phone = phone or company.whatsapp_phone or company.phone or company.mobile
        if not phone:
            return request.not_found()

        phone_clean = phone.replace(' ', '').replace('+', '')
        if not phone_clean.startswith('33'):
            return request.not_found()

        # Ajoute le lien du site dans le message
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        text = text or f"Bonjour, je vous contacte depuis votre site : {base_url}"
        text_encoded = quote(text)

        wa_url = f"https://wa.me/{phone_clean}?text={text_encoded}"
        return request.redirect(wa_url)
