# -*- coding: utf-8 -*-
# from odoo import http


# class WebsiteLinkChecker(http.Controller):
#     @http.route('/website_link_checker/website_link_checker', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/website_link_checker/website_link_checker/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('website_link_checker.listing', {
#             'root': '/website_link_checker/website_link_checker',
#             'objects': http.request.env['website_link_checker.website_link_checker'].search([]),
#         })

#     @http.route('/website_link_checker/website_link_checker/objects/<model("website_link_checker.website_link_checker"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('website_link_checker.object', {
#             'object': obj
#         })

