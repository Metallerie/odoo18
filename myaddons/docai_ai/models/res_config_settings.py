# -*- coding: utf-8 -*-
import os
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from google.cloud import documentai_v1 as documentai
except ImportError:
    documentai = None


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    docai_project_id = fields.Char("Google Project ID")
    docai_location = fields.Selection(
        [('eu', 'Europe'), ('us', 'USA')],
        default="eu",
        string="DocAI Location"
    )
    docai_key_path = fields.Char("Chemin clé JSON Google")
    docai_invoice_processor_id = fields.Char("DocAI Processor ID (Factures)")

    def set_values(self):
        res = super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('docai_ai.project_id', self.docai_project_id or "")
        ICP.set_param('docai_ai.location', self.docai_location or "eu")
        ICP.set_param('docai_ai.key_path', self.docai_key_path or "")
        ICP.set_param('docai_ai.invoice_processor_id', self.docai_invoice_processor_id or "")
        return res

    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        res.update(
            docai_project_id=ICP.get_param('docai_ai.project_id'),
            docai_location=ICP.get_param('docai_ai.location', 'eu'),
            docai_key_path=ICP.get_param('docai_ai.key_path'),
            docai_invoice_processor_id=ICP.get_param('docai_ai.invoice_processor_id'),
        )
        return res

    def action_test_docai_connection(self):
        """Teste la connexion avec Google Document AI"""
        ICP = self.env['ir.config_parameter'].sudo()
        project_id = ICP.get_param('docai_ai.project_id')
        location = ICP.get_param('docai_ai.location', 'eu')
        key_path = ICP.get_param('docai_ai.key_path')
        processor_id = ICP.get_param('docai_ai.invoice_processor_id')

        if not all([project_id, location, key_path, processor_id]):
            raise UserError("⚠️ Remplis tous les champs DocAI avant de tester.")

        if not os.path.exists(key_path):
            raise UserError(f"❌ Fichier de clé introuvable : {key_path}")

        if documentai is None:
            raise UserError("❌ Le package google-cloud-documentai n’est pas installé.\n"
                            "➡️ Installe-le avec : pip install google-cloud-documentai")

        try:
            # Fix : on exporte la variable pour gcloud
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

            client = documentai.DocumentProcessorServiceClient()
            processor_name = client.processor_path(project_id, location, processor_id)

            _logger.info("=== [DocAI Test] ===")
            _logger.info("Project ID : %s", project_id)
            _logger.info("Location   : %s", location)
            _logger.info("Processor  : %s", processor_id)
            _logger.info("Key Path   : %s", key_path)

            processor = client.get_processor(name=processor_name)
            _logger.info("DocAI Processor récupéré : %s (%s)", processor.display_name, processor.state.name)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': "Connexion réussie 🎉",
                    'message': f"✅ Connexion OK avec {processor.display_name} (state: {processor.state.name})",
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error("=== [DocAI Test] ERREUR === %s", e, exc_info=True)
            raise UserError(f"❌ Échec de connexion à Document AI : {e}")
