from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.tools import html_escape
from datetime import date


class VariantLandingController(WebsiteSale):

    @http.route(['/shop/<string:slug>-<int:variant_id>'], type='http', auth="public", website=True)
    def variant_product_page(self, slug, variant_id, **kwargs):
        ProductProduct = request.env['product.product'].sudo()
        variant = ProductProduct.browse(variant_id)

        if not variant.exists() or not variant.website_published:
            return request.not_found()

        template = variant.product_tmpl_id

        request.context = dict(request.context, product_id=variant.id)

        return request.render("website_sale.product", {
            'product': template,
            'variant': variant,
        })

    @http.route(['/sitemap_product_variant.xml'], type='http', auth='public', website=True, sitemap=False)
    def sitemap_product_variant(self, **kwargs):
        domain = [('website_published', '=', True)]
        variants = request.env['product.product'].sudo().search(domain)

        base_url = request.httprequest.host_url.rstrip('/')
        today = date.today().isoformat()

        urls = []
        for variant in variants:
            slug = variant.variant_slug or 'produit'
            url = f"{base_url}/shop/{slug}-{variant.id}"
            urls.append(f"""
                <url>
                    <loc>{html_escape(url)}</loc>
                    <lastmod>{today}</lastmod>
                    <changefreq>weekly</changefreq>
                    <priority>0.8</priority>
                </url>
            """)

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            {''.join(urls)}
        </urlset>"""

        return request.make_response(xml.strip(), headers=[('Content-Type', 'application/xml')])
