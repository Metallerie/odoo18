# -*- coding: utf-8 -*-
import logging
import base64
from odoo import models, api
from ..scripts.docai_client import DocAIClient

_logger = logging.getLogger(__name__)

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def _get_docai_config(self):
        """Récupère la configuration DocAI depuis res.config.settings"""
        ICP = self.env['ir.config_parameter'].sudo()
        project_id = ICP.get_param('docai_ai.project_id')
        processor_id = ICP.get_param('docai_ai.processor_id')
        location = ICP.get_param('docai_ai.location', 'eu')
        key_path = ICP.get_param('docai_ai.key_path')
        return project_id, processor_id, location, key_path

    def action_parse_docai(self):
        """Envoie le PDF à Google DocAI et retourne le JSON"""
        for attachment in self:
            if attachment.mimetype != "application/pdf":
                _logger.warning(f"DocAI ignoré : {attachment.name} n'est pas un PDF")
                continue

            # Récupérer config
            project_id, processor_id, location, key_path = self._get_docai_config()
            if not all([project_id, processor_id, location, key_path]):
                _logger.error("⚠️ Configuration DocAI incomplète dans res.config.settings")
                return False

            try:
                client = DocAIClient(
                    project_id=project_id,
                    processor_id=processor_id,
                    location=location,
                    key_path=key_path
                )

                # Décoder le PDF binaire
                file_content = base64.b64decode(attachment.datas)
                result = client.process_invoice(file_content)

                # Sauvegarder JSON dans un champ texte de la pièce jointe
                attachment.write({
                    'description': "Analyse DocAI effectuée",
                })

                # Retourne le JSON à l’appelant
                return result

            except Exception as e:
                _logger.error(f"Erreur appel DocAI pour {attachment.name}: {e}")
                return False
