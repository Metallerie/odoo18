from odoo import http
from odoo.http import request, Response
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.tools import html_escape
from datetime import date
from werkzeug.urls import url_encode
import re


def slug(value):
    """Transforme une chaîne en slug type URL"""
    value = str(value).lower()
    value = re.sub(r'[^\w\s-]', '', value)
    value = re.sub(r'[\s_-]+', '-', value)
    value = re.sub(r'^-+|-+$', '', value)
    return value


def keep(*args, **kwargs):
    return '?' + url_encode(kwargs)


def humanize_slug(slug_value):
    return slug_value.replace('-', ' ').capitalize()


class VariantLandingController(WebsiteSale):

    @http.route(['/shop/<string:category_slug>/<string:variant_slug>-<int:template_id>'], type='http', auth="public", website=True)
    def variant_product_page(self, category_slug, variant_slug, template_id, **kwargs):
        ProductTemplate = request.env['product.template'].sudo()
        ProductProduct = request.env['product.product'].sudo()

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

        category = template.public_categ_ids[:1]
        if category and slug(category[0].name) != category_slug:
            new_url = f"/shop/{slug(category[0].name)}/{variant_slug}-{template.id}"
            return request.redirect(new_url, code=301)

        # Nom lisible à partir du slug (pas brut)
        variant_name = humanize_slug(variant_slug)
        list_price = variant.list_price
        category_name = category[0].name if category else ""

        request.update_context(product_id=variant.id)

        seo_title = f"{variant_name} à partir de {list_price:.2f} €"
        meta_title = f"{template.name} > {variant_name} | {category_name}" if category_name else seo_title
        meta_description = f"Découvrez {variant_name} dans la catégorie {category_name}. Disponible à partir de {list_price:.2f} € TTC."

        canonical_url = template.website_url
        
        return request.render("website_sale.product", {
            'product': template,
            'variant': variant,
            'keep': keep,
            'meta_title': meta_title,
            'meta_description': meta_description,
            'canonical_url': canonical_url,
            'h1_title': seo_title,
        })

    @http.route(['/sitemap_product_variant.xml'], type='http', auth='public', website=True, sitemap=False)
    def variant_sitemap(self, **kwargs):
        ProductProduct = request.env['product.product'].sudo()
        variants = ProductProduct.search([
            ('website_published', '=', True),
            ('variant_slug', '!=', False)
        ])

        base_url = request.httprequest.host_url.rstrip('/')
        urls = []

        for variant in variants:
            slug_value = variant.variant_slug
            template = variant.product_tmpl_id
            template_id = template.id
            category = template.public_categ_ids[:1]
            if not category:
                continue
            url = f"{base_url}/shop/{slug(category[0].name)}/{slug_value}-{template_id}"
            lastmod = (variant.write_date or variant.create_date).date().isoformat()

            urls.append(f"""
                <url>
                    <loc>{html_escape(url)}</loc>
                    <lastmod>{lastmod}</lastmod>
                    <priority>0.8</priority>
                </url>
            """)

        sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            {''.join(urls)}
        </urlset>"""

        return Response(sitemap_content.strip(), content_type='application/xml;charset=utf-8')
