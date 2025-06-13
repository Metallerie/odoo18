from odoo import http
from odoo.http import request, Response
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.tools import html_escape
from datetime import date
from odoo.addons.website.controllers.main import Website
from werkzeug.urls import url_encode

def keep(**kwargs):
    """Simule la fonction keep_query d’Odoo pour conserver les paramètres d’URL."""
    return '?' + url_encode(kwargs)



class VariantLandingController(WebsiteSale):

    @http.route(['/shop/<string:variant_slug>-<int:template_id>'], type='http', auth="public", website=True)
    def variant_product_page(self, variant_slug, template_id, **kwargs):
        ProductTemplate = request.env['product.template'].sudo()
        ProductProduct = request.env['product.product'].sudo()

        template = ProductTemplate.browse(template_id)
        if not template.exists() or not template.website_published:
            return request.not_found()

        variant = ProductProduct.search([
            ('product_tmpl_id', '=', template.id),
            ('variant_slug', '=', variant_slug)
        ], limit=1)

        if not variant:
            return request.not_found()

        request.update_context(product_id=variant.id)

        return request.render("website_sale.product", {
            'product': template,
            'variant': variant,
            'keep': keep,  # ✅ Ici on injecte proprement la méthode
        })

    @http.route(['/sitemap_product_variant.xml'], type='http', auth='public', website=True, sitemap=False)
    def variant_sitemap(self, **kwargs):
        variants = request.env['product.product'].sudo().search([
            ('website_published', '=', True),
            ('variant_slug', '!=', False)
        ])

        base_url = request.httprequest.host_url.rstrip('/')
        today = date.today().isoformat()

        urls = []
        for variant in variants:
            slug = variant.variant_slug
            template_id = variant.product_tmpl_id.id
            url = f"{base_url}/shop/{slug}-{template_id}"
            urls.append(f"""
                <url>
                    <loc>{html_escape(url)}</loc>
                    <lastmod>{today}</lastmod>
                    <changefreq>weekly</changefreq>
                    <priority>0.8</priority>
                </url>
            """)

        sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            {''.join(urls)}
        </urlset>"""

        return Response(sitemap_content.strip(), content_type='application/xml;charset=utf-8')
