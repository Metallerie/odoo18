# -*- coding: utf-8 -*-
import os
import logging

from odoo import models, fields
from odoo.exceptions import UserError

try:
    from google.cloud import documentai
except ImportError:
    documentai = None

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    docai_project_id = fields.Char(string="Google Project ID")
    docai_location = fields.Char(string="Location", default="eu")
    docai_key_path = fields.Char(string="Chemin du fichier de clé JSON")

    def set_values(self):
        res = super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param("docai_ai.project_id", self.docai_project_id or "")
        ICP.set_param("docai_ai.location", self.docai_location or "eu")
        ICP.set_param("docai_ai.key_path", self.docai_key_path or "")
        return res

    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        res.update(
            docai_project_id=ICP.get_param("docai_ai.project_id", ""),
            docai_location=ICP.get_param("docai_ai.location", "eu"),
            docai_key_path=ICP.get_param("docai_ai.key_path", ""),
        )
        return res

    def action_test_docai_connection(self):
        """Teste la connexion à Google Document AI"""
        ICP = self.env['ir.config_parameter'].sudo()
        project_id = ICP.get_param("docai_ai.project_id")
        location = ICP.get_param("docai_ai.location", "eu")
        key_path = ICP.get_param("docai_ai.key_path")

        if not all([project_id, location, key_path]):
            raise UserError("⚠️ Remplis les champs Project ID, Location et Key Path avant de tester.")

        if not os.path.exists(key_path):
            raise UserError(f"❌ Fichier de clé introuvable : {key_path}")

        if documentai is None:
            raise UserError("❌ Package google-cloud-documentai manquant.\n➡️ pip install google-cloud-documentai")

        try:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
            client = documentai.DocumentProcessorServiceClient()

            parent = f"projects/{project_id}/locations/{location}"

            # Récupère seulement la première page de processors
            page_iter = client.list_processors(request={"parent": parent})
            first_page = next(page_iter.pages, None)
            nb = len(first_page.processors) if first_page else 0

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Connexion réussie 🎉",
                    "message": f"✅ API Document AI accessible ({nb} processors trouvés)",
                    "sticky": False,
                },
            }

        except Exception as e:
            _logger.error("=== [DocAI Test] ERREUR === %s", e, exc_info=True)
            raise UserError(f"❌ Échec de connexion à Document AI : {e}")
