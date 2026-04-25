# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class product_price_from_last_purchase(models.Model):
#     _name = 'product_price_from_last_purchase.product_price_from_last_purchase'
#     _description = 'product_price_from_last_purchase.product_price_from_last_purchase'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

