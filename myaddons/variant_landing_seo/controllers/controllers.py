from odoo import http
from odoo.http import request, Response
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.tools import html_escape
from datetime import date
from werkzeug.urls import url_encode


def keep(*args, **kwargs):
    return '?' + url_encode(kwargs)


class VariantLandingController(WebsiteSale):

    @http.route(['/shop/<string:category_slug>/<string:variant_slug>-<int:template_id>'], type='http', auth="public", website=True)
    def variant_product_page(self, category_slug, variant_slug, template_id, **kwargs):
        ProductTemplate = request.env['product.template'].sudo()
        ProductProduct = request.env['product.product'].sudo()
        Category = request.env['product.public.category'].sudo()
        slug = request.env['ir.http']._slug

        template = ProductTemplate.browse(template_id)
        if not template.exists() or not template.website_published:
            return request.not_found()

        variant = ProductProduct.search([
            ('product_tmpl_id', '=', template.id),
            ('variant_slug', '=', variant_slug),
            ('website_published', '=', True)
        ], limit=1)

        if not variant:
            return request.not_found()

        # Vérifie si le slug de la catégorie correspond à une des catégories réelles du template
        category_match = False
        for cat in template.public_categ_ids:
            if slug(cat) == category_slug:
                category_match = True
                break

        if not category_match:
            # Redirection douce vers l'URL correcte avec le bon slug de catégorie
            correct_slug = slug(template.public_categ_ids[0]) if template.public_categ_ids else 'uncategorized'
            return request.redirect(f"/shop/{correct_slug}/{variant_slug}-{template.id}", code=302)

        request.update_context(product_id=variant.id)
        return request.render("website_sale.product", {
            'product': template,
            'variant': variant,
            'keep': keep,
        })

    @http.route(['/sitemap_product_variant.xml'], type='http', auth='public', website=True, sitemap=False)
    def variant_sitemap(self, **kwargs):
        ProductProduct = request.env['product.product'].sudo()
        slug = request.env['ir.http']._slug
        variants = ProductProduct.search([
            ('website_published', '=', True),
            ('variant_slug', '!=', False)
        ])

        base_url = request.httprequest.host_url.rstrip('/')
        urls = []

        for variant in variants:
            template = variant.product_tmpl_id
            category = template.public_categ_ids[:1]  # prend la première catégorie s'il y en a
            category_slug = slug(category) if category else 'uncategorized'
            slug_value = variant.variant_slug
            template_id = template.id
            url = f"{base_url}/shop/{category_slug}/{slug_value}-{template_id}"
            lastmod = (variant.write_date or variant.create_date).date().isoformat()

            urls.append(f"""
                <url>
                    <loc>{html_escape(url)}</loc>
                    <lastmod>{lastmod}</lastmod>
                    <priority>0.8</priority>
                </url>
            """)

        sitemap_content = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
        <urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
            {''.join(urls)}
        </urlset>"""

        return Response(sitemap_content.strip(), content_type='application/xml;charset=utf-8')
