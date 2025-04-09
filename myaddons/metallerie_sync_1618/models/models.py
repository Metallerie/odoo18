# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class metallerie_sync_1617(models.Model):
#     _name = 'metallerie_sync_1617.metallerie_sync_1617'
#     _description = 'metallerie_sync_1617.metallerie_sync_1617'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

