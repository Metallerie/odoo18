# -*- coding: utf-8 -*-
import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Champs de config
    docai_project_id = fields.Char("Google Project ID")
    docai_location = fields.Char("Location")
    docai_key_path = fields.Char("Clé JSON")
    docai_invoice_processor_id = fields.Char("Processor Facture")
    docai_test_invoice_path = fields.Char("Facture de test")

    def action_test_docai_connection(self):
        """
        Méthode déclenchée par le bouton 'Tester connexion'
        """
        _logger.info("✅ Bouton Document AI cliqué avec paramètres :")
        _logger.info("   Project ID = %s", self.docai_project_id)
        _logger.info("   Location = %s", self.docai_location)
        _logger.info("   Key Path = %s", self.docai_key_path)
        _logger.info("   Processor Facture = %s", self.docai_invoice_processor_id)
        _logger.info("   Facture de test = %s", self.docai_test_invoice_path)

        # Message utilisateur
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Test Document AI",
                'message': "✅ Bouton bien déclenché ! (voir logs pour détails)",
                'sticky': False,
            }
        }
