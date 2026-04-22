# -*- coding: utf-8 -*-
# from odoo import http


# class ProductVariantPricelistImport(http.Controller):
#     @http.route('/product_variant_pricelist_import/product_variant_pricelist_import', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/product_variant_pricelist_import/product_variant_pricelist_import/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('product_variant_pricelist_import.listing', {
#             'root': '/product_variant_pricelist_import/product_variant_pricelist_import',
#             'objects': http.request.env['product_variant_pricelist_import.product_variant_pricelist_import'].search([]),
#         })

#     @http.route('/product_variant_pricelist_import/product_variant_pricelist_import/objects/<model("product_variant_pricelist_import.product_variant_pricelist_import"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('product_variant_pricelist_import.object', {
#             'object': obj
#         })

