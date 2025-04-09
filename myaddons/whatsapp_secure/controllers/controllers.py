from odoo import http
from odoo.http import request
from urllib.parse import quote
from werkzeug.utils import redirect
import logging

_logger = logging.getLogger(__name__)

class WhatsAppSecureController(http.Controller):

    @http.route(['/whatsapp/send'], type='http', auth='public', website=True)
    def send_whatsapp(self, **kwargs):
        company = request.env['res.company'].sudo().search([], limit=1)
        phone = company.whatsapp_phone or '33625159120'

        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url', default='http://localhost:8069')
        message = f"Bonjour, je vous contacte depuis votre site : {base_url}"
        message_encoded = quote(message)

        user_agent = request.httprequest.headers.get('User-Agent', '').lower()
        _logger.info(f"User-Agent détecté : {user_agent}")

        if 'mobile' in user_agent:
            redirect_url = f"https://api.whatsapp.com/send?phone={phone}&text={message_encoded}"
        else:
            redirect_url = f"https://web.whatsapp.com/send?phone={phone}&text={message_encoded}"

        _logger.info(f"Redirection WhatsApp vers : {redirect_url}")

        return redirect(redirect_url)
