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

    @http.route('/sitemap_product_variant.xml', type='http', auth='public', website=True)
    def variant_sitemap(self):
        products = request.env['product.product'].sudo().search([('website_published', '=', True)])

        xml_items = []
        today = date.today().isoformat()

        for product in products:
            url = f"https://www.metallerie.xyz/shop/{product.variant_slug or product.id}"
            xml_items.append(f"""
    <url>
        <loc>{url}</loc>
        <lastmod>{today}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>
    </url>
""")

        sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{''.join(xml_items)}
</urlset>
"""

        return Response(sitemap_content, content_type='application/xml;charset=utf-8')
