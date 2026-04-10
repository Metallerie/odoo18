from odoo import models
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = "account.move"

    def action_docai_scan_json(self):
    _logger.error("######## DOCAI BOUTON CLIQUÉ ########")
    raise UserError("Le bouton entre bien dans la méthode")
