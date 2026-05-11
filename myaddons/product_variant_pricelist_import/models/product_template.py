# product_template.py
# -*- coding: utf-8 -*-

from odoo import models


class ProductTemplate(models.Model):
    _inherit = "product.template"
    
    last_variant_import_date = fields.Datetime(
        string="Dernier import variantes"
    )

    def action_open_variant_pricelist_import_wizard(self):
        self.ensure_one()
         
        return {
            "type": "ir.actions.act_window",
            "name": "Import variantes et pricelist",
            "res_model": "product.variant.pricelist.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_template_id": self.id,
                "default_category_id": self.categ_id.id,
            },
        }
    
