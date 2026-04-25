# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    product_length = fields.Float(string="Longueur")
    product_width = fields.Float(string="Largeur")
    product_height = fields.Float(string="Hauteur")
    product_diameter = fields.Float(string="Diamètre")
    product_thickness = fields.Float(string="Épaisseur")
