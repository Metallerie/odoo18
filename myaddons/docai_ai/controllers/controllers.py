# -*- coding: utf-8 -*-
# from odoo import http


# class DocaiAi(http.Controller):
#     @http.route('/docai_ai/docai_ai', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/docai_ai/docai_ai/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('docai_ai.listing', {
#             'root': '/docai_ai/docai_ai',
#             'objects': http.request.env['docai_ai.docai_ai'].search([]),
#         })

#     @http.route('/docai_ai/docai_ai/objects/<model("docai_ai.docai_ai"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('docai_ai.object', {
#             'object': obj
#         })

