import logging
import mimetypes

from odoo import fields, models, _
from odoo.exceptions import UserError

# flake8: noqa: E501

_logger = logging.getLogger(__name__)


class ImportHelper(models.TransientModel):
    _inherit = 'base_import.helper'

    url = fields.Char(
        default='https://www.google.com/basepages/producttype/taxonomy-with-ids.en-US.txt',
        help='Specify the Google Taxonomy URL to download a list of all Google product categories (only Plain text .txt)',
        required=True,
    )
    mode = fields.Selection(selection_add=[('google_categ', 'Google category')])

    def action_import(self):
        self.ensure_one()
        if self.mode != 'google_categ':
            return super(ImportHelper, self).action_import()

        mimetype, encoding = mimetypes.guess_type(self.url)
        if mimetype != 'text/plain':
            raise UserError(_('Only the Plain text (.txt) format is allowed.'))

        res = self.open_url(self.url)
        if res['error']:
            raise UserError(_('Error opening URL: %s') % res['error'])
        content = res['content']

        index = 1
        for line in content.split('\n'):

            # Skip comments
            if line[:1] == '#':
                continue

            elif line:
                code, category = line.split(' - ', 1)
                category_hierarchy = category.split(' > ')
                vals = {
                    'name': category_hierarchy[-1:][0],
                    'code': code,
                    'sequence': index,
                }
                if len(category_hierarchy) > 1:
                    parent_category = self.env['product.google.category'].search([
                        ('name', '=', category_hierarchy[-2:-1][0]),
                    ])
                    vals['parent_id'] = parent_category.id

                google_category = self.env['product.google.category'].search([
                    ('code', '=', code),
                ])
                if not google_category:
                    self.env['product.google.category'].create(vals)
                elif self.do_rewrite:
                    google_category.write(vals)
            index += 1

        return {
            'name': _('Google Categories'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.google.category',
            'view_mode': 'list,form',
            'target': 'current',
        }
