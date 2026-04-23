# -*- coding: utf-8 -*-
# from odoo import http


# class WebsiteNumericOptions(http.Controller):
#     @http.route('/website_numeric_options/website_numeric_options', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/website_numeric_options/website_numeric_options/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('website_numeric_options.listing', {
#             'root': '/website_numeric_options/website_numeric_options',
#             'objects': http.request.env['website_numeric_options.website_numeric_options'].search([]),
#         })

#     @http.route('/website_numeric_options/website_numeric_options/objects/<model("website_numeric_options.website_numeric_options"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('website_numeric_options.object', {
#             'object': obj
#         })

