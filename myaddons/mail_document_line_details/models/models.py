# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class mail_document_line_details(models.Model):
#     _name = 'mail_document_line_details.mail_document_line_details'
#     _description = 'mail_document_line_details.mail_document_line_details'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

