# -*- coding: utf-8 -*-
import os
from odoo import models, fields, api
from odoo.exceptions import UserError

try:
    from google.cloud import documentai_v1 as documentai
except ImportError:
    documentai = None


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    docai_project_id = fields.Char(string="Project ID")
    docai_location = fields.Char(string="Location", default="eu")
    docai_key_path = fields.Char(string="Clé JSON")
    docai_invoice_processor_id = fields.Char(string="Processor Facture")
    docai_test_invoice_path = fields.Char(string="Facture de test")

    def set_values(self):
        super().set_values()
        ir_config = self.env['ir.config_parameter'].sudo()
        ir_config.set_param("docai_ai.project_id", self.docai_project_id or "")
        ir_config.set_param("docai_ai.location", self.docai_location or "eu")
        ir_config.set_param("docai_ai.key_path", self.docai_key_path or "")
        ir_config.set_param("docai_ai.invoice_processor_id", self.docai_invoice_processor_id or "")
        ir_config.set_param("docai_ai.test_invoice_path", self.docai_test_invoice_path or "")

    @api.model
    def get_values(self):
        res = super().get_values()
        ir_config = self.env['ir.config_parameter'].sudo()
        res.update(
            docai_project_id=ir_config.get_param("docai_ai.project_id", ""),
            docai_location=ir_config.get_param("docai_ai.location", "eu"),
            docai_key_path=ir_config.get_param("docai_ai.key_path", ""),
            docai_invoice_processor_id=ir_config.get_param("docai_ai.invoice_processor_id", ""),
            docai_test_invoice_path=ir_config.get_param("docai_ai.test_invoice_path", ""),
        )
        return res

    def action_test_docai_connection(self):
        print("⚡ [DocAI Test] Bouton déclenché !")
        print("   ➤ Project ID:", self.docai_project_id)
        print("   ➤ Location:", self.docai_location)
        print("   ➤ Key Path:", self.docai_key_path)
        print("   ➤ Processor ID:", self.docai_invoice_processor_id)
        print("   ➤ Facture test:", self.docai_test_invoice_path)

        if not documentai:
            raise UserError("⚠️ google-cloud-documentai n'est pas installé dans ton venv.")

        if not self.docai_project_id or not self.docai_invoice_processor_id:
            raise UserError("⚠️ Paramètres Document AI manquants.")

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.docai_key_path

        client = documentai.DocumentProcessorServiceClient(
            client_options={"api_endpoint": f"{self.docai_location}-documentai.googleapis.com"}
        )

        name = f"projects/{self.docai_project_id}/locations/{self.docai_location}/processors/{self.docai_invoice_processor_id}"

        if not self.docai_test_invoice_path:
            raise UserError("⚠️ Aucun fichier test défini.")

        with open(self.docai_test_invoice_path, "rb") as f:
            pdf_content = f.read()

        raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)

        try:
            result = client.process_document(request=request)
            print("✅ Réponse Document AI reçue")
            print("   → Extrait (texte brut) :", result.document.text[:200])
        except Exception as e:
            print("❌ Erreur connexion Document AI :", str(e))
            raise UserError(f"Echec connexion Document AI: {e}")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Test Document AI",
                'message': "✅ Bouton bien déclenché (voir logs pour détails avec print)",
                'type': 'success',
                'sticky': False,
            }
        }
