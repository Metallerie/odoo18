# -*- coding: utf-8 -*-
import logging
import os
from odoo import models, fields, api
from odoo.exceptions import UserError

from google.cloud import documentai_v1 as documentai

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    docai_project_id = fields.Char("Google Project ID")
    docai_location = fields.Char("Location", default="eu")
    docai_key_path = fields.Char("Chemin Clé JSON")
    docai_invoice_processor_id = fields.Char("Processor Facture ID")
    docai_test_invoice_path = fields.Char("Facture de test")

    # Sauvegarde des valeurs
    def set_values(self):
        res = super(ResConfigSettings, self).set_values()
        self.env["ir.config_parameter"].sudo().set_param("docai_ai.docai_project_id", self.docai_project_id or "")
        self.env["ir.config_parameter"].sudo().set_param("docai_ai.docai_location", self.docai_location or "")
        self.env["ir.config_parameter"].sudo().set_param("docai_ai.docai_key_path", self.docai_key_path or "")
        self.env["ir.config_parameter"].sudo().set_param("docai_ai.docai_invoice_processor_id", self.docai_invoice_processor_id or "")
        self.env["ir.config_parameter"].sudo().set_param("docai_ai.docai_test_invoice_path", self.docai_test_invoice_path or "")
        return res

    # Récupération des valeurs
    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env["ir.config_parameter"].sudo()
        res.update(
            docai_project_id=params.get_param("docai_ai.docai_project_id", default=""),
            docai_location=params.get_param("docai_ai.docai_location", default="eu"),
            docai_key_path=params.get_param("docai_ai.docai_key_path", default=""),
            docai_invoice_processor_id=params.get_param("docai_ai.docai_invoice_processor_id", default=""),
            docai_test_invoice_path=params.get_param("docai_ai.docai_test_invoice_path", default=""),
        )
        return res

    # Test connexion Google Document AI
    def action_test_docai_connection(self):
        self.ensure_one()
        _logger.info("⚡ [DocAI Test] Bouton déclenché !")
        _logger.info("   ➤ Project ID: %s", self.docai_project_id)
        _logger.info("   ➤ Location: %s", self.docai_location)
        _logger.info("   ➤ Key Path: %s", self.docai_key_path)
        _logger.info("   ➤ Processor ID: %s", self.docai_invoice_processor_id)
        _logger.info("   ➤ Facture test: %s", self.docai_test_invoice_path)

        try:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.docai_key_path

            client = documentai.DocumentProcessorServiceClient(
                client_options={"api_endpoint": f"{self.docai_location}-documentai.googleapis.com"}
            )

            name = f"projects/{self.docai_project_id}/locations/{self.docai_location}/processors/{self.docai_invoice_processor_id}"
            _logger.info("⚡ [DocAI Test] Processor Name généré : %s", name)

            # Charger la facture de test
            with open(self.docai_test_invoice_path, "rb") as f:
                pdf_content = f.read()

            raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")
            request = documentai.ProcessRequest(name=name, raw_document=raw_document)

            result = client.process_document(request=request)

            _logger.info("✅ [DocAI Test] Connexion réussie, texte détecté : %s", result.document.text[:200])
            return True

        except Exception as e:
            _logger.error("❌ Erreur connexion Document AI : %s", str(e))
            raise UserError(f"Echec connexion Document AI : {str(e)}")
