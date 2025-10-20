# -*- coding: utf-8 -*-
import logging
import os
from odoo import models, fields, api
from google.cloud import documentai_v1 as documentai

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Champs de config
    docai_project_id = fields.Char("DocAI Project ID")
    docai_location = fields.Char("DocAI Location", default="eu")
    docai_key_path = fields.Char("DocAI Key Path")
    docai_invoice_processor_id = fields.Char("DocAI Processor Facture")
    docai_test_invoice_path = fields.Char("DocAI Facture de test")

    # Charger les valeurs depuis ir.config_parameter
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        res.update(
            docai_project_id=ICP.get_param("docai_ai.docai_project_id", ""),
            docai_location=ICP.get_param("docai_ai.docai_location", "eu"),
            docai_key_path=ICP.get_param("docai_ai.docai_key_path", ""),
            docai_invoice_processor_id=ICP.get_param("docai_ai.docai_invoice_processor_id", ""),
            docai_test_invoice_path=ICP.get_param("docai_ai.docai_test_invoice_path", ""),
        )
        return res

    # Sauvegarder les valeurs dans ir.config_parameter
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("docai_ai.docai_project_id", self.docai_project_id or "")
        ICP.set_param("docai_ai.docai_location", self.docai_location or "eu")
        ICP.set_param("docai_ai.docai_key_path", self.docai_key_path or "")
        ICP.set_param("docai_ai.docai_invoice_processor_id", self.docai_invoice_processor_id or "")
        ICP.set_param("docai_ai.docai_test_invoice_path", self.docai_test_invoice_path or "")

    # Bouton de test connexion
    def action_test_docai_connection(self):
        try:
            project_id = self.docai_project_id
            location = self.docai_location
            processor_id = self.docai_invoice_processor_id
            key_path = self.docai_key_path
            test_file = self.docai_test_invoice_path

            if not all([project_id, location, processor_id, key_path, test_file]):
                raise ValueError("⚠️ Paramètres manquants pour tester la connexion DocAI.")

            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

            client = documentai.DocumentProcessorServiceClient(
                client_options={"api_endpoint": f"{location}-documentai.googleapis.com"}
            )
            name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

            with open(test_file, "rb") as f:
                pdf_content = f.read()

            raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")
            request = documentai.ProcessRequest(name=name, raw_document=raw_document)
            result = client.process_document(request=request)

            # Si tout marche
            msg = f"✅ Connexion OK — {len(result.document.text)} caractères extraits."
            _logger.info(msg)

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": "Document AI", "message": msg, "sticky": False},
            }

        except Exception as e:
            error_msg = f"❌ Erreur connexion Document AI : {str(e)}"
            _logger.error(error_msg, exc_info=True)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": "Document AI", "message": error_msg, "sticky": True},
            }
