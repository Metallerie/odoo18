# -*- coding: utf-8 -*-
# from odoo import http


# class PurchaseFrequencyReport(http.Controller):
#     @http.route('/purchase_frequency_report/purchase_frequency_report', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/purchase_frequency_report/purchase_frequency_report/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('purchase_frequency_report.listing', {
#             'root': '/purchase_frequency_report/purchase_frequency_report',
#             'objects': http.request.env['purchase_frequency_report.purchase_frequency_report'].search([]),
#         })

#     @http.route('/purchase_frequency_report/purchase_frequency_report/objects/<model("purchase_frequency_report.purchase_frequency_report"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('purchase_frequency_report.object', {
#             'object': obj
#         })

