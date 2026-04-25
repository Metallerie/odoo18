# -*- coding: utf-8 -*-
# from odoo import http


# class ProductPriceFromLastPurchase(http.Controller):
#     @http.route('/product_price_from_last_purchase/product_price_from_last_purchase', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/product_price_from_last_purchase/product_price_from_last_purchase/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('product_price_from_last_purchase.listing', {
#             'root': '/product_price_from_last_purchase/product_price_from_last_purchase',
#             'objects': http.request.env['product_price_from_last_purchase.product_price_from_last_purchase'].search([]),
#         })

#     @http.route('/product_price_from_last_purchase/product_price_from_last_purchase/objects/<model("product_price_from_last_purchase.product_price_from_last_purchase"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('product_price_from_last_purchase.object', {
#             'object': obj
#         })

