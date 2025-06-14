# -*- coding: utf-8 -*-
from odoo import http, fields, models
from odoo.http import request
import base64, datetime, re
from hashlib import md5
import logging

_logger = logging.getLogger(__name__)

# Monkey patch global pour corriger url_root partout (http → https)
from werkzeug.wrappers.request import Request as WerkzeugRequest
_original_url_root = WerkzeugRequest.url_root.fget

def patched_url_root(self):
    return _original_url_root(self).replace("http://", "https://")

WerkzeugRequest.url_root = property(patched_url_root)


class RobotsAndSitemapHttpsController(http.Controller):

    @http.route('/robots.txt', type='http', auth='public', website=True, sitemap=False)
    def robots_txt(self, **kwargs):
        https_url = request.httprequest.url_root.rstrip("/")

        lines = [
            "User-agent: *",
            "Disallow: /web/",
            "Disallow: /web/login",
            "Disallow: /web/signup",
            "Disallow: /web/session/",
            "Disallow: /website/info",
            "Disallow: /website/translations",
            "Disallow: /website/seo_sitemap",
            "Disallow: /mail/",
            "Disallow: /im_livechat/",
            "Disallow: /calendar/",
            "Disallow: /shop/cart",
            "Disallow: /shop/checkout",
            "Disallow: /shop/payment",
            "Disallow: /shop/confirm_order",
            "Disallow: /shop/address",
            "Disallow: /shop/thankyou",
            "Disallow: /*?*",
            "Clean-param: unique&utm_source&utm_medium&utm_campaign&fbclid&gclid",
            f"Sitemap: {https_url}/sitemap.xml"
        ]

        custom_sitemaps = request.env['ir.config_parameter'].sudo().get_param('website.sitemap_urls', '')
        for extra in custom_sitemaps.split(','):
            extra = extra.strip()
            if extra:
                lines.append(f"Sitemap: {extra}")

        robots_model = request.env['website.robots'].sudo()
        custom_lines = robots_model.search([]).mapped('content')
        if custom_lines:
            lines += ["", "##############", "#   custom   #", "##############"]
            lines += custom_lines

        lines.append("")
        return request.make_response("\n".join(lines), headers=[("Content-Type", "text/plain")])

    @http.route('/sitemap.xml', type='http', auth='public', website=True, multilang=False, sitemap=False)
    def sitemap_xml_index(self, **kwargs):
        current_website = request.website
        Attachment = request.env['ir.attachment'].sudo()
        View = request.env['ir.ui.view'].sudo()
        mimetype = 'application/xml;charset=utf-8'
        content = None

        url_root = request.httprequest.url_root
        _logger.warning("📡 url_root corrigé (monkey patch) = %s", url_root)

        hashed_url_root = md5(url_root.encode()).hexdigest()[:8]
        sitemap_base_url = '/sitemap-%d-%s' % (current_website.id, hashed_url_root)

        def create_sitemap(url, content):
            return Attachment.create({
                'raw': content.encode(),
                'mimetype': mimetype,
                'type': 'binary',
                'name': url,
                'url': url,
            })

        force = kwargs.get('force')
        dom = [('url', '=', '%s.xml' % sitemap_base_url), ('type', '=', 'binary')]
        sitemap = Attachment.search(dom, limit=1)
        if sitemap and not force:
            create_date = fields.Datetime.from_string(sitemap.create_date)
            delta = datetime.datetime.now() - create_date
            if delta < datetime.timedelta(seconds=0):
                content = base64.b64decode(sitemap.datas)

        if not content:
            dom = [('type', '=', 'binary'), '|', ('url', '=like', '%s-%%.xml' % sitemap_base_url),
                   ('url', '=', '%s.xml' % sitemap_base_url)]
            sitemaps = Attachment.search(dom)
            sitemaps.unlink()

            locs = request.website.with_user(request.website.user_id)._enumerate_pages()
            EXCLUDE_REGEX = re.compile(r'/website/info|/feed|/whatsapp/send')
            locs = list(filter(lambda loc: not EXCLUDE_REGEX.search(loc['loc']), locs))

            values = {
                'locs': locs,
                'url_root': url_root.rstrip("/"),
            }
            urls = View._render_template('website.sitemap_locs', values)

            if urls.strip():
                content = View._render_template('website.sitemap_xml', {'content': urls})
                create_sitemap('%s.xml' % sitemap_base_url, content)
            else:
                return request.not_found()

        return request.make_response(content, [('Content-Type', mimetype)])
