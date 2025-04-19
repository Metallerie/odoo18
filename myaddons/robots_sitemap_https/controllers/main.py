# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.http import request
import base64, datetime
from hashlib import md5
from itertools import islice
import logging

_logger = logging.getLogger(__name__)

LOC_PER_SITEMAP = 45000  # nombre de liens max par sitemap

# Monkey patch global pour corriger url_root partout
from werkzeug.wrappers.request import Request as WerkzeugRequest
_original_url_root = WerkzeugRequest.url_root.fget

def patched_url_root(self):
    return _original_url_root(self).replace("http://", "https://")

WerkzeugRequest.url_root = property(patched_url_root)

class RobotsAndSitemapHttpsController(http.Controller):

    @http.route('/robots.txt', type='http', auth='public', website=True, sitemap=False)
    def robots_txt(self, **kwargs):
        https_url = request.httprequest.url_root.rstrip("/")
        robots_txt_content = request.env['website'].get_current_website().robots_content
        if robots_txt_content:
            robots_txt_content = robots_txt_content.replace("http://", "https://")
            return request.make_response(robots_txt_content, headers=[("Content-Type", "text/plain")])

        lines = [
            "User-agent: *",
            f"Sitemap: {https_url}/sitemap.xml",
            "",
            "##############",
            "#   custom   #",
            "##############",
            
        ]
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

        dom = [('url', '=', '%s.xml' % sitemap_base_url), ('type', '=', 'binary')]
        sitemap = Attachment.search(dom, limit=1)
        if sitemap:
            create_date = fields.Datetime.from_string(sitemap.create_date)
            delta = datetime.datetime.now() - create_date
            if delta < datetime.timedelta(seconds=0):
                content = base64.b64decode(sitemap.datas)

        if not content:
            dom = [('type', '=', 'binary'), '|', ('url', '=like', '%s-%%.xml' % sitemap_base_url),
                   ('url', '=', '%s.xml' % sitemap_base_url)]
            sitemaps = Attachment.search(dom)
            sitemaps.unlink()

            pages = 0
            locs = request.website.with_user(request.website.user_id)._enumerate_pages()
            while True:
                values = {
                    'locs': islice(locs, 0, LOC_PER_SITEMAP),
                    'url_root': url_root.rstrip("/"),
                }
                urls = View._render_template('website.sitemap_locs', values)
                if urls.strip():
                    content = View._render_template('website.sitemap_xml', {'content': urls})
                    pages += 1
                    last_sitemap = create_sitemap('%s-%d.xml' % (sitemap_base_url, pages), content)
                else:
                    break

            if not pages:
                return request.not_found()
            elif pages == 1:
                last_sitemap.write({
                    'url': "%s.xml" % sitemap_base_url,
                    'name': "%s.xml" % sitemap_base_url,
                })
            else:
                pages_with_website = ["%d-%s-%d" % (current_website.id, hashed_url_root, p) for p in range(1, pages + 1)]
                content = View._render_template('website.sitemap_index_xml', {
                    'pages': pages_with_website,
                    'url_root': url_root.rstrip("/"),
                })
                create_sitemap('%s.xml' % sitemap_base_url, content)

        return request.make_response(content, [('Content-Type', mimetype)])
