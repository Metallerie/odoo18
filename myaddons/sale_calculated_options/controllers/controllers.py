# -*- coding: utf-8 -*-
# from odoo import http


# class SaleCalculatedOptions(http.Controller):
#     @http.route('/sale_calculated_options/sale_calculated_options', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/sale_calculated_options/sale_calculated_options/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('sale_calculated_options.listing', {
#             'root': '/sale_calculated_options/sale_calculated_options',
#             'objects': http.request.env['sale_calculated_options.sale_calculated_options'].search([]),
#         })

#     @http.route('/sale_calculated_options/sale_calculated_options/objects/<model("sale_calculated_options.sale_calculated_options"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('sale_calculated_options.object', {
#             'object': obj
#         })

