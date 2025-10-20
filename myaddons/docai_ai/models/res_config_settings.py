# -*- coding: utf-8 -*-
import logging
import os

from odoo import models, fields
from odoo.exceptions import UserError

from google.cloud import documentai_v1 as documentai

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Champs de configuration
    docai_project_id = fields.Char(string="Project ID", config_parameter="docai_ai.project_id")
    docai_location = fields.Char(string="Location", default="eu", config_parameter="docai_ai.location")
    docai_key_path = fields.Char(string="Clé JSON", config_parameter="docai_ai.key_path")
    docai_invoice_processor_id = fields.Char(string="Processor Factures", config_parameter="docai_ai.invoice_processor_id")
    docai_test_invoice_path = fields.Char(string="Facture test (PDF)", config_parameter="docai_ai.test_invoice_path")

    def action_test_docai_connection(self):
        """ Teste la connexion à Google Document AI avec la facture de test """
        self.ensure_one()

        if not (self.docai_project_id and self.docai_location and self.docai_key_path and self.docai_invoice_processor_id):
            raise UserError("⚠️ Merci de remplir Project ID, Location, Key JSON et Processor ID avant de tester.")

        if not self.docai_test_invoice_path:
            raise UserError("⚠️ Merci de définir un chemin vers une facture test (PDF).")

        # Charger la clé d’API
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.docai_key_path

        # Construire client avec endpoint forcé
        client = documentai.DocumentProcessorServiceClient(
            client_options={"api_endpoint": f"{self.docai_location}-documentai.googleapis.com"}
        )

        # Nom complet du processor
        name = f"projects/{self.docai_project_id}/locations/{self.docai_location}/processors/{self.docai_invoice_processor_id}"

        # Charger la facture test
        try:
            with open(self.docai_test_invoice_path, "rb") as f:
                pdf_content = f.read()
        except Exception as e:
            raise UserError(f"Impossible de lire le fichier test : {e}")

        raw_document = documentai.RawDocument(
            content=pdf_content,
            mime_type="application/pdf"
        )

        request = documentai.ProcessRequest(name=name, raw_document=raw_document)

        try:
            result = client.process_document(request=request)
            document = result.document
            _logger.info("=== DocAI Test Réussi ===")
            _logger.info(document.text[:500])  # log les 500 premiers caractères

            # Retour visuel Odoo
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "✅ Succès connexion DocAI",
                    "message": "Texte extrait de la facture : %s" % document.text[:120],
                    "sticky": False,
                }
            }

        except Exception as e:
            _logger.error("❌ Erreur connexion Document AI : %s", e)
            raise UserError(f"❌ Erreur connexion Document AI : {e}")
