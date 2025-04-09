# -*- coding: utf-8 -*-
# from odoo import http


# class MetallerieSync1617(http.Controller):
#     @http.route('/metallerie_sync_1617/metallerie_sync_1617', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/metallerie_sync_1617/metallerie_sync_1617/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('metallerie_sync_1617.listing', {
#             'root': '/metallerie_sync_1617/metallerie_sync_1617',
#             'objects': http.request.env['metallerie_sync_1617.metallerie_sync_1617'].search([]),
#         })

#     @http.route('/metallerie_sync_1617/metallerie_sync_1617/objects/<model("metallerie_sync_1617.metallerie_sync_1617"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('metallerie_sync_1617.object', {
#             'object': obj
#         })

