# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Champs de config Google Document AI
    docai_project_id = fields.Char(string="Project ID")
    docai_location = fields.Char(string="Location", default="eu")
    docai_key_path = fields.Char(string="Chemin Clé JSON")
    docai_invoice_processor_id = fields.Char(string="Processor Factures")
    docai_test_invoice_path = fields.Char(string="Facture Test (PDF)")

    # Lecture des paramètres stockés
    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        res.update(
            docai_project_id=ICP.get_param("docai_ai.docai_project_id", default=""),
            docai_location=ICP.get_param("docai_ai.docai_location", default="eu"),
            docai_key_path=ICP.get_param("docai_ai.docai_key_path", default=""),
            docai_invoice_processor_id=ICP.get_param("docai_ai.docai_invoice_processor_id", default=""),
            docai_test_invoice_path=ICP.get_param("docai_ai.docai_test_invoice_path", default=""),
        )
        return res

    # Sauvegarde des paramètres
    def set_values(self):
        super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("docai_ai.docai_project_id", self.docai_project_id or "")
        ICP.set_param("docai_ai.docai_location", self.docai_location or "eu")
        ICP.set_param("docai_ai.docai_key_path", self.docai_key_path or "")
        ICP.set_param("docai_ai.docai_invoice_processor_id", self.docai_invoice_processor_id or "")
        ICP.set_param("docai_ai.docai_test_invoice_path", self.docai_test_invoice_path or "")

    # Bouton de test de connexion
    def action_test_docai_connection(self):
        import os
        from google.cloud import documentai_v1 as documentai

        project_id = self.docai_project_id
        location = self.docai_location
        processor_id = self.docai_invoice_processor_id
        key_path = self.docai_key_path
        test_invoice = self.docai_test_invoice_path

        if not project_id or not location or not processor_id or not key_path:
            raise UserError("⚠️ Paramètres Document AI incomplets.")

        if not test_invoice or not os.path.exists(test_invoice):
            raise UserError("⚠️ Aucune facture de test trouvée. Vérifie le chemin.")

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

        client = documentai.DocumentProcessorServiceClient(
            client_options={"api_endpoint": f"{location}-documentai.googleapis.com"}
        )
        name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

        with open(test_invoice, "rb") as f:
            pdf_content = f.read()

        raw_document = documentai.RawDocument(
            content=pdf_content,
            mime_type="application/pdf"
        )
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)

        try:
            result = client.process_document(request=request)
            doc = result.document
            _logger.info("✅ Connexion Document AI OK - Texte extrait: %s", doc.text[:200])
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Succès",
                    "message": "✅ Connexion OK - Champs extraits: %s" % ", ".join(
                        [e.type_ for e in doc.entities[:5]]
                    ),
                    "sticky": False,
                },
            }
        except Exception as e:
            _logger.error("❌ Erreur connexion Document AI : %s", e)
            raise UserError("❌ Erreur connexion Document AI : %s" % e)
