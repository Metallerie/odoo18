# -*- coding: utf-8 -*-

import os
import logging
from odoo import models, fields, api
from google.cloud import documentai_v1 as documentai

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Champs configurables
    docai_project_id = fields.Char("Project ID")
    docai_location = fields.Char("Location", default="eu")
    docai_key_path = fields.Char("Chemin Clé JSON")
    docai_invoice_processor_id = fields.Char("Processor Facture")
    docai_test_invoice_path = fields.Char("Facture de test")

    # Charger depuis ir.config_parameter
    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        res.update(
            docai_project_id=ICP.get_param("docai_ai.project_id", default=""),
            docai_location=ICP.get_param("docai_ai.location", default="eu"),
            docai_key_path=ICP.get_param("docai_ai.key_path", default=""),
            docai_invoice_processor_id=ICP.get_param("docai_ai.invoice_processor_id", default=""),
            docai_test_invoice_path=ICP.get_param("docai_ai.test_invoice_path", default=""),
        )
        return res

    # Sauvegarde dans ir.config_parameter
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("docai_ai.project_id", self.docai_project_id or "")
        ICP.set_param("docai_ai.location", self.docai_location or "eu")
        ICP.set_param("docai_ai.key_path", self.docai_key_path or "")
        ICP.set_param("docai_ai.invoice_processor_id", self.docai_invoice_processor_id or "")
        ICP.set_param("docai_ai.test_invoice_path", self.docai_test_invoice_path or "")

    # Bouton : Test connexion Document AI
    def action_test_docai_connection(self):
        self.ensure_one()

        project_id = (self.docai_project_id or "").strip()
        location = (self.docai_location or "eu").strip()
        key_path = (self.docai_key_path or "").strip()
        processor_id = (self.docai_invoice_processor_id or "").strip()
        test_invoice = (self.docai_test_invoice_path or "").strip()

        name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

        # --- PRINT console ---
        print("\n=== ⚡ VARIABLES ENVOYÉES À DOCUMENT AI ===")
        print(f"Project ID   : {project_id}")
        print(f"Location     : {location}")
        print(f"Key Path     : {key_path}")
        print(f"Processor ID : {processor_id}")
        print(f"Test Invoice : {test_invoice}")
        print(f"Processor Name complet : {name}")
        print("==========================================\n")

        try:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

            client = documentai.DocumentProcessorServiceClient(
                client_options={"api_endpoint": f"{location}-documentai.googleapis.com"}
            )

            with open(test_invoice, "rb") as f:
                pdf_content = f.read()

            raw_document = documentai.RawDocument(
                content=pdf_content,
                mime_type="application/pdf"
            )

            request = documentai.ProcessRequest(name=name, raw_document=raw_document)
            result = client.process_document(request=request)

            document = result.document
            print("✅ Connexion réussie !")
            print("📄 Extrait texte détecté :")
            print(document.text[:500])

            return True

        except Exception as e:
            print("❌ Erreur connexion Document AI :", str(e))
            _logger.error("❌ Erreur connexion Document AI : %s", str(e))
            return False
