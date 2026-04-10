from odoo import models
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
_logger.warning("######## account_move.py DOCAI CHARGÉ ########")

class AccountMove(models.Model):
    _inherit = "account.move"

def action_docai_scan_json(self):
    for move in self:
        _logger.warning("######## DOCAI BOUTON CLIQUÉ ########")

        source_json = move.docai_json_raw or move.docai_json
        _logger.warning("[DocAI] source_json present = %s", bool(source_json))

        if not source_json:
            raise UserError("Aucun JSON trouvé.")

        data = json.loads(source_json)

        _logger.warning("[DocAI] invoice_id = %s", data.get("invoice_id"))
        _logger.warning("[DocAI] invoice_date = %s", data.get("invoice_date"))
        _logger.warning("[DocAI] supplier_name = %s", data.get("supplier_name"))
        _logger.warning("[DocAI] nb line_items = %s", len(data.get("line_items") or []))

        raise UserError("Lecture JSON OK")
