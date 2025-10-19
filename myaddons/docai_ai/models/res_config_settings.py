# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Champs configurables (stockés dans ir.config_parameter)
    docai_project_id = fields.Char(
        string="Project ID",
        config_parameter="docai_ai.project_id"
    )
    docai_location = fields.Char(
        string="Location",
        default="eu",
        config_parameter="docai_ai.location"
    )
    docai_key_path = fields.Char(
        string="Chemin fichier JSON clé API",
        config_parameter="docai_ai.key_path"
    )
    docai_invoice_processor_id = fields.Char(
        string="Processor Facture",
        config_parameter="docai_ai.invoice_processor_id"
    )
    docai_test_invoice_path = fields.Char(
        string="Facture de test (PDF)",
        config_parameter="docai_ai.test_invoice_path"
    )

    # Bouton "Tester connexion"
    def action_test_docai_connection(self):
        """Test la connexion à Google Document AI avec les paramètres saisis"""
        project_id = self.docai_project_id
        location = self.docai_location or "eu"
        processor_id = self.docai_invoice_processor_id
        key_path = self.docai_key_path
        test_invoice = self.docai_test_invoice_path

        if not project_id or not location or not processor_id or not key_path:
            raise ValueError("⚠️ Merci de configurer tous les champs obligatoires (Project, Location, Key, Processor).")

        _logger.info("=== [DocAI Test] ===")
        _logger.info(f"Project: {project_id}, Location: {location}, Processor: {processor_id}")
        _logger.info(f"Key path: {key_path}")
        if test_invoice:
            _logger.info(f"Facture test: {test_invoice}")

        try:
            from google.cloud import documentai_v1 as documentai
            import os

            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

            client = documentai.DocumentProcessorServiceClient(
                client_options={"api_endpoint": f"{location}-documentai.googleapis.com"}
            )

            name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"
            _logger.info(f"[DocAI] Test avec processor name = {name}")

            if test_invoice:
                with open(test_invoice, "rb") as f:
                    pdf_content = f.read()
                raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")
                request = documentai.ProcessRequest(name=name, raw_document=raw_document)
                result = client.process_document(request=request)
                text_detected = result.document.text[:300]
                _logger.info(f"✅ Connexion OK - extrait du texte: {text_detected}")
            else:
                # Juste un ping si pas de fichier de test
                processors = list(client.list_processors(parent=f"projects/{project_id}/locations/{location}"))
                _logger.info(f"✅ Connexion OK - {len(processors)} processeurs détectés")

        except Exception as e:
            _logger.error(f"❌ Erreur connexion Document AI : {e}")
            raise
