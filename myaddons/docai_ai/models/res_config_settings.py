# -*- coding: utf-8 -*-
import os
import logging
from odoo import models, fields
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

    def set_values(self):
        res = super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('docai_ai.project_id', self.docai_project_id or "")
        ICP.set_param('docai_ai.location', self.docai_location or "eu")
        ICP.set_param('docai_ai.key_path', self.docai_key_path or "")
        return res

    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        res.update(
            docai_project_id=ICP.get_param('docai_ai.project_id'),
            docai_location=ICP.get_param('docai_ai.location', 'eu'),
            docai_key_path=ICP.get_param('docai_ai.key_path'),
        )
        return res

    def action_test_docai_connection(self):
        """Teste juste la connexion à l’API Document AI"""
        ICP = self.env['ir.config_parameter'].sudo()
        project_id = ICP.get_param('docai_ai.project_id')
        location = ICP.get_param('docai_ai.location', 'eu')
        key_path = ICP.get_param('docai_ai.key_path')

        if not all([project_id, location, key_path]):
            raise UserError("⚠️ Remplis les champs Google Project ID, Location et Key Path avant de tester.")

        if not os.path.exists(key_path):
            raise UserError(f"❌ Fichier de clé introuvable : {key_path}")

        if documentai is None:
            raise UserError("❌ Package google-cloud-documentai manquant.\n"
                            "➡️ pip install google-cloud-documentai")

        try:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
            client = documentai.DocumentProcessorServiceClient()

            parent = f"projects/{project_id}/locations/{location}"
            processors = list(client.list_processors(parent=parent))

            _logger.info("=== [DocAI Test] ===")
            _logger.info("Connexion OK, %d processors trouvés.", len(processors))

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': "Connexion réussie 🎉",
                    'message': f"✅ API Document AI accessible ({len(processors)} processors détectés)",
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error("=== [DocAI Test] ERREUR === %s", e, exc_info=True)
            raise UserError(f"❌ Échec de connexion à Document AI : {e}")
