from odoo import models
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
_logger.warning("######## account_move.py DOCAI CHARGÉ ########")

class AccountMove(models.Model):
    _inherit = "account.move"

    def action_docai_scan_json(self):
        _logger.error("######## DOCAI BOUTON CLIQUÉ ########")
        raise UserError("Le bouton entre bien dans la méthode")
