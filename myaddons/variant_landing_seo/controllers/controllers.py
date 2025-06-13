# -*- coding: utf-8 -*-
# from odoo import http


# class VariantLandingSeo(http.Controller):
#     @http.route('/variant_landing_seo/variant_landing_seo', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/variant_landing_seo/variant_landing_seo/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('variant_landing_seo.listing', {
#             'root': '/variant_landing_seo/variant_landing_seo',
#             'objects': http.request.env['variant_landing_seo.variant_landing_seo'].search([]),
#         })

#     @http.route('/variant_landing_seo/variant_landing_seo/objects/<model("variant_landing_seo.variant_landing_seo"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('variant_landing_seo.object', {
#             'object': obj
#         })

