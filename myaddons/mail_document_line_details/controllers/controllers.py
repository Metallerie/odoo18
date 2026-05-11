# -*- coding: utf-8 -*-
# from odoo import http


# class MailDocumentLineDetails(http.Controller):
#     @http.route('/mail_document_line_details/mail_document_line_details', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/mail_document_line_details/mail_document_line_details/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('mail_document_line_details.listing', {
#             'root': '/mail_document_line_details/mail_document_line_details',
#             'objects': http.request.env['mail_document_line_details.mail_document_line_details'].search([]),
#         })

#     @http.route('/mail_document_line_details/mail_document_line_details/objects/<model("mail_document_line_details.mail_document_line_details"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('mail_document_line_details.object', {
#             'object': obj
#         })

