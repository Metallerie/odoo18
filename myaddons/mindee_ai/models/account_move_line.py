# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    is_unassigned = fields.Boolean(string="Produit non affecté", default=False)

    def action_assign_product(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.assign.line.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_id': self.id,
                'default_ocr_description': self.name,
            },
        }


class ProductAssignLineWizard(models.TransientModel):
    _name = 'product.assign.line.wizard'
    _description = "Affecter un produit existant à une ligne de facture"

    line_id = fields.Many2one('account.move.line', string="Ligne de facture", required=True, readonly=True)
    product_id = fields.Many2one('product.product', string="Produit à affecter", required=True)
    ocr_description = fields.Char(string="Description OCR", readonly=True)

    def action_validate_assignment(self):
        self.ensure_one()
        self.line_id.write({
            'product_id': self.product_id.id,
            'name': self.ocr_description,
            'is_unassigned': False,
        })
        return {'type': 'ir.actions.act_window_close'}
