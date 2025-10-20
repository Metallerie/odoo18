# -*- coding: utf-8 -*-
import logging
import os
from odoo import models, fields
from odoo.exceptions import UserError

from google.cloud import documentai_v1 as documentai

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Champs configurables
    docai_project_id = fields.Char("Google Project ID")
    docai_location = fields.Char("Location", default="eu")
    docai_key_path = fields.Char("Chemin fichier clé JSON")
    docai_invoice_processor_id = fields.Char("Processor ID Factures")
    docai_test_invoice_path = fields.Char("Chemin facture test")

    def set_values(self):
        super().set_values()
        self.env["ir.config_parameter"].sudo().set_param("docai_ai.docai_project_id", self.docai_project_id or "")
        self.env["ir.config_parameter"].sudo().set_param("docai_ai.docai_location", self.docai_location or "eu")
        self.env["ir.config_parameter"].sudo().set_param("docai_ai.docai_key_path", self.docai_key_path or "")
        self.env["ir.config_parameter"].sudo().set_param("docai_ai.docai_invoice_processor_id", self.docai_invoice_processor_id or "")
        self.env["ir.config_parameter"].sudo().set_param("docai_ai.docai_test_invoice_path", self.docai_test_invoice_path or "")

    @classmethod
    def get_values(cls):
        res = super().get_values()
        ICP = cls.env["ir.config_parameter"].sudo()
        res.update(
            docai_project_id=ICP.get_param("docai_ai.docai_project_id", default=""),
            docai_location=ICP.get_param("docai_ai.docai_location", default="eu"),
            docai_key_path=ICP.get_param("docai_ai.docai_key_path", default=""),
            docai_invoice_processor_id=ICP.get_param("docai_ai.docai_invoice_processor_id", default=""),
            docai_test_invoice_path=ICP.get_param("docai_ai.docai_test_invoice_path", default=""),
        )
        return res

    def action_test_docai_connection(self):
        """Test de connexion à Google Document AI avec la facture de test"""
        try:
            if not self.docai_project_id or not self.docai_invoice_processor_id:
                raise UserError("⚠️ Project ID et Processor ID sont obligatoires")

            if not self.docai_key_path or not os.path.exists(self.docai_key_path):
                raise UserError(f"⚠️ Fichier clé JSON introuvable : {self.docai_key_path}")

            if not self.docai_test_invoice_path or not os.path.exists(self.docai_test_invoice_path):
                raise UserError(f"⚠️ Facture test introuvable : {self.docai_test_invoice_path}")

            # Authentification
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.docai_key_path

            # Endpoint forcé (ex: eu-documentai.googleapis.com)
            api_endpoint = f"{self.docai_location}-documentai.googleapis.com"
            client = documentai.DocumentProcessorServiceClient(
                client_options={"api_endpoint": api_endpoint}
            )

            # Nom du processor
            name = f"projects/{self.docai_project_id}/locations/{self.docai_location}/processors/{self.docai_invoice_processor_id}"

            # DEBUG
            _logger.info("=== [DocAI DEBUG] ===")
            _logger.info("Endpoint utilisé : %s", api_endpoint)
            _logger.info("Processor name   : %s", name)
            _logger.info("Clé JSON         : %s", self.docai_key_path)
            _logger.info("Facture test     : %s", self.docai_test_invoice_path)

            # Charger le PDF
            with open(self.docai_test_invoice_path, "rb") as f:
                pdf_content = f.read()

            raw_document = documentai.RawDocument(
                content=pdf_content,
                mime_type="application/pdf"
            )

            # Requête
            request = documentai.ProcessRequest(name=name, raw_document=raw_document)
            result = client.process_document(request=request)

            document = result.document

            _logger.info("=== [DocAI RESULT - Texte détecté] ===\n%s", document.text[:500])
            for entity in document.entities:
                _logger.info("Champ %s → %s", entity.type_, entity.mention_text)

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Succès",
                    "message": "Connexion à Google Document AI réussie ✅",
                    "sticky": False,
                },
            }

        except Exception as e:
            _logger.error("❌ Erreur connexion Document AI : %s", e, exc_info=True)
            raise UserError(f"❌ Échec de connexion à Document AI : {str(e)}")
