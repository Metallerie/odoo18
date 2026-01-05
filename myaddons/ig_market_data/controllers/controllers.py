# -*- coding: utf-8 -*-
# from odoo import http


# class Myaddons/igMarketData(http.Controller):
#     @http.route('/myaddons/ig_market_data/myaddons/ig_market_data', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/myaddons/ig_market_data/myaddons/ig_market_data/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('myaddons/ig_market_data.listing', {
#             'root': '/myaddons/ig_market_data/myaddons/ig_market_data',
#             'objects': http.request.env['myaddons/ig_market_data.myaddons/ig_market_data'].search([]),
#         })

#     @http.route('/myaddons/ig_market_data/myaddons/ig_market_data/objects/<model("myaddons/ig_market_data.myaddons/ig_market_data"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('myaddons/ig_market_data.object', {
#             'object': obj
#         })

