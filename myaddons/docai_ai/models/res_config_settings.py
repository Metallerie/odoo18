# -*- coding: utf-8 -*-
import logging
import base64
from odoo import models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from google.cloud import documentai_v1 as documentai
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except ImportError:
    documentai = None


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    docai_project_id = fields.Char("Google Project ID")
    docai_location = fields.Selection(
        [('eu', 'Europe'), ('us', 'USA')],
        default="eu",
        string="DocAI Location"
    )
    docai_key_path = fields.Char("Chemin clé JSON Google")
    docai_invoice_processor_id = fields.Char("DocAI Processor ID (Factures)")
    docai_test_invoice_path = fields.Char("Facture test (PDF)")

    def set_values(self):
        res = super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('docai_ai.project_id', self.docai_project_id)
        ICP.set_param('docai_ai.location', self.docai_location)
        ICP.set_param('docai_ai.key_path', self.docai_key_path)
        ICP.set_param('docai_ai.invoice_processor_id', self.docai_invoice_processor_id)
        ICP.set_param('docai_ai.test_invoice_path', self.docai_test_invoice_path)
        return res

    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        res.update(
            docai_project_id=ICP.get_param('docai_ai.project_id'),
            docai_location=ICP.get_param('docai_ai.location', 'eu'),
            docai_key_path=ICP.get_param('docai_ai.key_path'),
            docai_invoice_processor_id=ICP.get_param('docai_ai.invoice_processor_id'),
            docai_test_invoice_path=ICP.get_param('docai_ai.test_invoice_path'),
        )
        return res

    def action_test_docai_connection(self):
        """Test de connexion avec Document AI"""
        ICP = self.env['ir.config_parameter'].sudo()
        project_id = ICP.get_param('docai_ai.project_id')
        location = ICP.get_param('docai_ai.location', 'eu')
        key_path = ICP.get_param('docai_ai.key_path')
        processor_id = ICP.get_param('docai_ai.invoice_processor_id')
        test_invoice_path = ICP.get_param('docai_ai.test_invoice_path')

        if not all([project_id, location, key_path, processor_id, test_invoice_path]):
            raise UserError("⚠️ Remplis tous les champs DocAI (clé JSON, projet, location, processor, facture test).")

        if documentai is None:
            raise UserError("⚠️ Installe google-cloud-documentai et google-api-python-client.")

        name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

        # Essai 1 : gRPC
        try:
            _logger.info("🔄 [DocAI Test] Tentative gRPC avec endpoint %s", location)

            client = documentai.DocumentProcessorServiceClient.from_service_account_file(
                key_path,
                client_options={"api_endpoint": f"{location}-documentai.googleapis.com"}
            )

            with open(test_invoice_path, "rb") as f:
                raw_document = documentai.RawDocument(content=f.read(), mime_type="application/pdf")

            request = documentai.ProcessRequest(name=name, raw_document=raw_document)
            result = client.process_document(request=request)

            doc_text = result.document.text[:200]
            _logger.info("✅ [DocAI Test] Connexion gRPC OK, extrait : %s", doc_text)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': "Connexion réussie (gRPC) 🎉",
                    'message': f"Extrait : {doc_text}",
                    'sticky': False,
                }
            }

        except Exception as grpc_err:
            _logger.warning("⚠️ Erreur gRPC (%s), fallback REST", grpc_err)

            # Essai 2 : REST
            try:
                creds = service_account.Credentials.from_service_account_file(
                    key_path,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                service = build("documentai", "v1", credentials=creds)

                with open(test_invoice_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")

                request = {"rawDocument": {"content": encoded, "mimeType": "application/pdf"}}
                result = service.projects().locations().processors().process(
                    name=name, body=request
                ).execute()

                doc_text = result.get("document", {}).get("text", "")[:200]
                _logger.info("✅ [DocAI Test] Connexion REST OK, extrait : %s", doc_text)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': "Connexion réussie (REST) 🎉",
                        'message': f"Extrait : {doc_text}",
                        'sticky': False,
                    }
                }
            except Exception as rest_err:
                _logger.error("❌ Erreur REST : %s", rest_err)
                raise UserError(f"❌ Échec de connexion à Document AI (REST) : {rest_err}")
