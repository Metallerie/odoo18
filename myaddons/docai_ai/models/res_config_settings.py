from odoo import models, fields, api, _
from odoo.exceptions import UserError
import os
import logging
from google.cloud import documentai_v1 as documentai

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    docai_project_id = fields.Char("Project ID")
    docai_location = fields.Char("Location", default="eu")
    docai_key_path = fields.Char("Chemin Clé JSON")
    docai_invoice_processor_id = fields.Char("Processor Facture")
    docai_test_invoice_path = fields.Char("Facture de test")

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        res.update(
            docai_project_id=ICP.get_param("docai_ai.project_id", ""),
            docai_location=ICP.get_param("docai_ai.location", "eu"),
            docai_key_path=ICP.get_param("docai_ai.key_path", ""),
            docai_invoice_processor_id=ICP.get_param("docai_ai.invoice_processor_id", ""),
            docai_test_invoice_path=ICP.get_param("docai_ai.test_invoice_path", ""),
        )
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("docai_ai.project_id", self.docai_project_id or "")
        ICP.set_param("docai_ai.location", self.docai_location or "eu")
        ICP.set_param("docai_ai.key_path", self.docai_key_path or "")
        ICP.set_param("docai_ai.invoice_processor_id", self.docai_invoice_processor_id or "")
        ICP.set_param("docai_ai.test_invoice_path", self.docai_test_invoice_path or "")

    def action_test_docai_connection(self):
        self.ensure_one()

        project_id = (self.docai_project_id or "").strip()
        location = (self.docai_location or "eu").strip()
        key_path = (self.docai_key_path or "").strip()
        processor_id = (self.docai_invoice_processor_id or "").strip()
        test_invoice = (self.docai_test_invoice_path or "").strip()

        name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

        try:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

            client = documentai.DocumentProcessorServiceClient(
                client_options={"api_endpoint": f"{location}-documentai.googleapis.com"}
            )

            with open(test_invoice, "rb") as f:
                pdf_content = f.read()

            raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")
            request = documentai.ProcessRequest(name=name, raw_document=raw_document)
            result = client.process_document(request=request)

            document = result.document
            sample_text = document.text[:300].replace("\n", " ")

            msg = _("✅ Connexion réussie à Google Document AI !\nExtrait : %s") % sample_text
            _logger.info(msg)

            # Retourne une notification à l’utilisateur
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Test Document AI"),
                    "message": msg,
                    "sticky": False,
                    "type": "success",
                },
            }

        except Exception as e:
            msg = _("❌ Erreur connexion Document AI : %s") % str(e)
            _logger.error(msg)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Test Document AI"),
                    "message": msg,
                    "sticky": True,
                    "type": "danger",
                },
            }
