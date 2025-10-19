# -*- coding: utf-8 -*-
import logging
import traceback
from odoo import models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except ImportError:
    service_account = None
    build = None


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

    # Bouton de test connexion (REST)
    def action_test_docai_connection(self):
        """Teste la connexion avec Google Document AI via REST (plus stable que gRPC)"""
        ICP = self.env['ir.config_parameter'].sudo()
        project_id = ICP.get_param('docai_ai.project_id')
        location = ICP.get_param('docai_ai.location', 'eu')
        key_path = ICP.get_param('docai_ai.key_path')

        _logger.info("=== [DocAI Test REST] Début du test connexion ===")
        _logger.info("Project ID: %s", project_id)
        _logger.info("Location: %s", location)
        _logger.info("Key path: %s", key_path)

        if not all([project_id, location, key_path]):
            raise UserError("Veuillez remplir tous les champs DocAI avant de tester la connexion.")

        if service_account is None or build is None:
            raise UserError("Les packages google-auth et google-api-python-client ne sont pas installés. "
                            "Installe-les avec : pip install google-auth google-auth-oauthlib google-api-python-client")

        try:
            # Charger credentials
            _logger.info("Chargement des credentials depuis: %s", key_path)
            credentials = service_account.Credentials.from_service_account_file(key_path)

            # Construire client REST Document AI
            service = build("documentai", "v1", credentials=credentials, cache_discovery=False)

            parent = f"projects/{project_id}/locations/{location}"
            _logger.info("Requête REST sur: %s", parent)

            # Liste des processors via REST
            processors = service.projects().locations().processors().list(parent=parent).execute()

            if "processors" not in processors or not processors["processors"]:
                raise UserError("Aucun processor trouvé dans ce projet.")

            first_proc = processors["processors"][0]
            display_name = first_proc.get("displayName", "Inconnu")
            state = first_proc.get("state", "INCONNU")

            _logger.info("Premier processor REST: %s (state=%s)", display_name, state)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': "Connexion réussie 🎉",
                    'message': f"Processor trouvé (REST) : {display_name} "
                               f"(état: {state}, région: {location})",
                    'sticky': False,
                }
            }

        except Exception as e:
            full_error = traceback.format_exc()
            _logger.error("=== [DocAI Test REST] ERREUR ===\n%s", full_error)
            raise UserError(f"Echec de connexion à Document AI (REST) : {str(e)}")
