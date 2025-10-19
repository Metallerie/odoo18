# -*- coding: utf-8 -*-
import logging
import traceback
from odoo import models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from google.cloud import documentai_v1 as documentai
    from google.oauth2 import service_account
except ImportError:
    documentai = None
    service_account = None


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Champs de configuration
    docai_project_id = fields.Char("Google Project ID")
    docai_location = fields.Selection(
        [('eu', 'Europe'), ('us', 'USA')],
        default="eu",
        string="DocAI Location"
    )
    docai_key_path = fields.Char("Chemin clé JSON Google")
    docai_invoice_processor_id = fields.Char("DocAI Processor ID (Factures)")
    docai_receipt_processor_id = fields.Char("DocAI Processor ID (Reçus)")

    # Sauvegarde des valeurs
    def set_values(self):
        res = super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('docai_ai.project_id', self.docai_project_id or "")
        ICP.set_param('docai_ai.location', self.docai_location or "eu")
        ICP.set_param('docai_ai.key_path', self.docai_key_path or "")
        ICP.set_param('docai_ai.invoice_processor_id', self.docai_invoice_processor_id or "")
        ICP.set_param('docai_ai.receipt_processor_id', self.docai_receipt_processor_id or "")
        return res

    # Chargement des valeurs
    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        res.update(
            docai_project_id=ICP.get_param('docai_ai.project_id'),
            docai_location=ICP.get_param('docai_ai.location', 'eu'),
            docai_key_path=ICP.get_param('docai_ai.key_path'),
            docai_invoice_processor_id=ICP.get_param('docai_ai.invoice_processor_id'),
            docai_receipt_processor_id=ICP.get_param('docai_ai.receipt_processor_id'),
        )
        return res

    # Bouton de test connexion
    def action_test_docai_connection(self):
        """Teste la connexion avec Google Document AI via list_processors (plus léger que get_processor)"""
        ICP = self.env['ir.config_parameter'].sudo()
        project_id = ICP.get_param('docai_ai.project_id')
        location = ICP.get_param('docai_ai.location', 'eu')
        key_path = ICP.get_param('docai_ai.key_path
