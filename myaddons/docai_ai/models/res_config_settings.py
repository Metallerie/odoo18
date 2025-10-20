# -*- coding: utf-8 -*-
import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    docai_project_id = fields.Char(string="Project ID")
    docai_location = fields.Char(string="Location", default="eu")
    docai_key_path = fields.Char(string="Clé JSON")
    docai_invoice_processor_id = fields.Char(string="Processor Facture")
    docai_test_invoice_path = fields.Char(string="Facture de test")

    def action_test_docai_connection(self):
        _logger.info("⚡ Bouton Test DocAI déclenché !")
        _logger.info("   ➤ Project ID: %s", self.docai_project_id)
        _logger.info("   ➤ Location: %s", self.docai_location)
        _logger.info("   ➤ Key Path: %s", self.docai_key_path)
        _logger.info("   ➤ Processor ID: %s", self.docai_invoice_processor_id)
        _logger.info("   ➤ Facture test: %s", self.docai_test_invoice_path)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Test Document AI",
                'message': "⚡ Variables envoyées → voir odoo-server.log",
                'type': 'success',
                'sticky': False,
            }
        }
