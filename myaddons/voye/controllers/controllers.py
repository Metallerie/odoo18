# -*- coding: utf-8 -*-
# from odoo import http


# class Voye(http.Controller):
#     @http.route('/voye/voye', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/voye/voye/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('voye.listing', {
#             'root': '/voye/voye',
#             'objects': http.request.env['voye.voye'].search([]),
#         })

#     @http.route('/voye/voye/objects/<model("voye.voye"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('voye.object', {
#             'object': obj
#         })

