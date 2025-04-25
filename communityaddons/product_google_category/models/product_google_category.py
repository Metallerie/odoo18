# Copyright © 2021 Garazd Creation (<https://garazd.biz>)
# @author: Yurii Razumovskyi (<support@garazd.biz>)
# @author: Iryna Razumovska (<support@garazd.biz>)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductGoogleCategory(models.Model):
    _name = "product.google.category"
    _description = 'Google Product Category'
    _parent_store = True
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(index=True)
    code = fields.Char(required=True, readonly=True)
    parent_id = fields.Many2one(
        string="Parent Category",
        comodel_name='product.google.category',
        ondelete="cascade",
        index=True,
    )
    parent_path = fields.Char(index=True)
    child_id = fields.One2many(
        string="Children Categories",
        comodel_name='product.google.category',
        inverse_name='parent_id',
    )
    parents_and_self = fields.Many2many(
        comodel_name='product.google.category',
        compute='_compute_parents_and_self',
    )

    #=== COMPUTE METHODS ===#

    def _compute_parents_and_self(self):
        for category in self:
            if category.parent_path:
                category.parents_and_self = self.env['product.google.category'].browse([int(p) for p in category.parent_path.split('/')[:-1]])
            else:
                category.parents_and_self = category

    @api.depends('parents_and_self')
    def _compute_display_name(self):
        for category in self:
            category.display_name = " > ".join(category.parents_and_self.mapped('name'))

    #=== CONSTRAINT METHODS ===#

    @api.constrains('parent_id')
    def check_parent_id(self):
        if self._has_cycle():
            raise ValueError(self.env._("Error! You cannot create recursive categories."))

    @api.constrains('code')
    def _check_code(self):
        for category in self:
            if self.search_count([('code', '=', category.code)]) > 1:
                raise ValidationError(_('The code of the Google category must be unique.'))

    # === BUSINESS METHODS ===#

    def unlink(self):
        self.child_id.parent_id = None
        return super(ProductGoogleCategory, self).unlink()

