import os
import logging
import requests
from odoo import models, fields
from odoo.exceptions import UserError
from google.oauth2 import service_account
from google.auth.transport.requests import Request

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    docai_project_id = fields.Char(string="Google Project ID")
    docai_location = fields.Char(string="Location", default="eu")
    docai_key_path = fields.Char(string="Chemin du fichier de clé JSON")

    def action_test_docai_connection(self):
        """Teste la connexion à Google Document AI (REST au lieu de gRPC)"""
        ICP = self.env['ir.config_parameter'].sudo()
        project_id = ICP.get_param("docai_ai.project_id")
        location = ICP.get_param("docai_ai.location", "eu")
        key_path = ICP.get_param("docai_ai.key_path")

        if not all([project_id, location, key_path]):
            raise UserError("⚠️ Remplis Project ID, Location et Key Path avant de tester.")

        if not os.path.exists(key_path):
            raise UserError(f"❌ Fichier de clé introuvable : {key_path}")

        try:
            # Auth avec clé JSON
            creds = service_account.Credentials.from_service_account_file(
                key_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            creds.refresh(Request())
            access_token = creds.token

            # Appel REST à Document AI
            url = f"https://{location}-documentai.googleapis.com/v1/projects/{project_id}/locations/{location}/processors"
            headers = {"Authorization": f"Bearer {access_token}"}
            resp = requests.get(url, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                nb = len(data.get("processors", []))
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": "Connexion réussie 🎉",
                        "message": f"✅ API Document AI accessible ({nb} processors trouvés)",
                        "sticky": False,
                    },
                }
            else:
                raise UserError(f"❌ Erreur REST {resp.status_code}: {resp.text}")

        except Exception as e:
            _logger.error("=== [DocAI Test] ERREUR === %s", e, exc_info=True)
            raise UserError(f"❌ Échec de connexion à Document AI : {e}")
