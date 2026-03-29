# -*- coding: utf-8 -*-
# from odoo import http


# class ProductSupplierinfoLastBill(http.Controller):
#     @http.route('/product_supplierinfo_last_bill/product_supplierinfo_last_bill', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/product_supplierinfo_last_bill/product_supplierinfo_last_bill/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('product_supplierinfo_last_bill.listing', {
#             'root': '/product_supplierinfo_last_bill/product_supplierinfo_last_bill',
#             'objects': http.request.env['product_supplierinfo_last_bill.product_supplierinfo_last_bill'].search([]),
#         })

#     @http.route('/product_supplierinfo_last_bill/product_supplierinfo_last_bill/objects/<model("product_supplierinfo_last_bill.product_supplierinfo_last_bill"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('product_supplierinfo_last_bill.object', {
#             'object': obj
#         })

