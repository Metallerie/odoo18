# Copyright © 2021 Garazd Creation (<https://garazd.biz>)
# @author: Yurii Razumovskyi (<support@garazd.biz>)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).

import logging
from typing import Dict
import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ImportHelper(models.TransientModel):
    _name = 'base_import.helper'
    _description = 'Import Helper'

    mode = fields.Selection(selection=[])
    do_rewrite = fields.Boolean(
        string='Rewrite',
        help='Rewrite object names in the "Update" mode.',
        default=True,
    )
    url = fields.Char(string='URL')
    help_url = fields.Char(string='Help URL', readonly=True)
    file = fields.Binary()

    @api.model
    def open_url(self, url, mode='text', headers: Dict = None, verify: bool = True) -> Dict:
        error = None
        content = None
        try:
            response = requests.get(
                url,
                params=None,
                headers=headers or {},
                timeout=30,
                verify=verify,
            )
            response.raise_for_status()
            content = response.text if mode == 'text' else response
        except requests.HTTPError as e:
            _logger.debug(
                "Error opening URL (failed with code: %r, msg: %r, content: %r)",
                e.response.status_code, e.response.reason, e.response.content,
            )
            error = '%s %s' % (e.response.status_code, e.response.reason)
        return {
            'content': content,
            'error': error,
        }

    def action_import(self):
        self.ensure_one()

    def action_open_help_url(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.help_url,
            'target': 'new',
            'target_type': 'public',
        }
