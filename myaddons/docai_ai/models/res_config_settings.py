# myaddons/docai_ai/models/res_config_settings.py
# -*- coding: utf-8 -*-

import os
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError
from google.cloud import documentai_v1 as documentai

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    docai_project_id = fields.Char("Google Project ID")
    docai_location = fields.Char("DocAI Location", default="eu")
    docai_key_path = fields.Char("Chemin clé JSON")
    docai_invoice_processor_id = fields.Char("Processor Factures ID")
    docai_test_invoice_path = fields.Char("Facture de test (PDF)")

    def action_test_docai_connection(self):
        """Teste la connexion à Document AI avec une facture de test"""
        project_id = self.docai_project_id
        location = self.docai_location or "eu"
        processor_id = self.docai_invoice_processor_id
        key_path = self.docai_key_path
        file_path = self.docai_test_invoice_path

        if not (project_id and location and processor_id and key_path and file_path):
            raise UserError("⚠️ Merci de remplir tous les champs (Project, Location, Processor, Key, Facture test).")

        # Authentification
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

        try:
            # ⚡ Client forcé sur EU
            client = documentai.DocumentProcessorServiceClient(
                client_options={"api_endpoint": f"{location}-documentai.googleapis.com"}
            )
            name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

            # Charger le PDF de test
            with open(file_path, "rb") as f:
                pdf_content = f.read()

            raw_document = documentai.RawDocument(
                content=pdf_content,
                mime_type="application/pdf"
            )
            request = documentai.ProcessRequest(name=name, raw_document=raw_document)
            result = client.process_document(request=request)

            # Résumé des infos extraites
            doc = result.document
            extrait = []
            for entity in doc.entities[:5]:  # limite aux 5 premiers champs
                extrait.append(f"{entity.type_}: {entity.mention_text}")

            msg = "✅ Connexion réussie à Google Document AI !\n\nChamps extraits :\n" + "\n".join(extrait)
            _logger.info(msg)
            raise UserError(msg)  # affichage dans Odoo

        except Exception as e:
            _logger.error("❌ Erreur DocAI Test : %s", e)
            raise UserError(f"❌ Échec de connexion à Document AI : {str(e)}")
