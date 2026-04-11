# -*- coding: utf-8 -*-

import logging
from odoo import models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _docai_process_line_items(self, data):
        self.ensure_one()

        line_items = data.get("line_items", [])
        if not line_items:
            _logger.info("[DocAI] Aucun line_items pour move %s", self.id)
            return

        _logger.info("[DocAI] %s line_items détectés pour move %s", len(line_items), self.id)

        # on codera ici la suite
        for item in line_items:
            _logger.info("[DocAI] item: %s", item)
