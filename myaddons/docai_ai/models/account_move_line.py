from odoo import models
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _docai_process_line_items(self, data):
        self.ensure_one()

        line_items = data.get("line_items", [])
        if not line_items:
            _logger.info("[DocAI] Aucun line_items pour move %s", self.id)
            return

        # traitement des lignes ici
