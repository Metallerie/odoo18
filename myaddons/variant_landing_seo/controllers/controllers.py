from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

class VariantLandingController(WebsiteSale):

    @http.route(['/shop/<string:slug>-<int:variant_id>'], type='http', auth="public", website=True)
    def variant_product_page(self, slug, variant_id, **kwargs):
        ProductProduct = request.env['product.product'].sudo()
        variant = ProductProduct.browse(variant_id)

        if not variant.exists() or not variant.website_published:
            return request.not_found()

        template = variant.product_tmpl_id

        # Injecte la variante dans le contexte pour forcer l'affichage
        request.context = dict(request.context, product_id=variant.id)

        return request.render("website_sale.product", {
            'product': template,
            'variant': variant,
        })
