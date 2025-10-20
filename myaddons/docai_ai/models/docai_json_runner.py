# -*- coding: utf-8 -*-
import base64
import os
import logging
from odoo import models, fields, _
from odoo.exceptions import UserError
from google.cloud import documentai_v1 as documentai

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    docai_json = fields.Text("JSON brut DocAI", readonly=True)

    def action_docai_analyze_attachment(self):
        """Envoie la pièce jointe PDF de la facture à Document AI et stocke le JSON brut"""
        for move in self:
            # 🔎 Récupérer le PDF lié à la facture
            attachment = self.env["ir.attachment"].search([
                ("res_model", "=", "account.move"),
                ("res_id", "=", move.id),
                ("mimetype", "=", "application/pdf")
            ], limit=1)

            if not attachment:
                raise UserError(_("Aucun PDF trouvé pour cette facture."))

            # ⚙️ Charger config DocAI
            ICP = self.env["ir.config_parameter"].sudo()
            project_id = ICP.get_param("docai_ai.project_id")
            location = ICP.get_param("docai_ai.location", "eu")
            key_path = ICP.get_param("docai_ai.key_path")
            processor_id = ICP.get_param("docai_ai.invoice_processor_id")

            if not all([project_id, location, key_path, processor_id]):
                raise UserError(_("Configuration Document AI incomplète."))

            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
            name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

            try:
                # 🚀 Client Document AI
                client = documentai.DocumentProcessorServiceClient(
                    client_options={"api_endpoint": f"{location}-documentai.googleapis.com"}
                )

                pdf_content = base64.b64decode(attachment.datas)
                raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")
                request = documentai.ProcessRequest(name=name, raw_document=raw_document)
                result = client.process_document(request=request)

                # 📦 Stocker JSON brut
                raw_json = documentai.Document.to_json(result.document)
                move.docai_json = raw_json

                _logger.info(f"✅ Facture {move.id} analysée par DocAI, JSON stocké")

            except Exception as e:
                _logger.error("❌ Erreur DocAI : %s", e)
                raise UserError(_("Erreur analyse Document AI : %s") % e)
