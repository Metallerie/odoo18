# -*- coding: utf-8 -*-
import logging
import os

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from google.cloud import documentai
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
    docai_receipt_processor_id = fields.Char("DocAI Processor ID (Reçus)")
    docai_test_invoice_path = fields.Char("Chemin facture test")

    def set_values(self):
        res = super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('docai_ai.project_id', self.docai_project_id)
        ICP.set_param('docai_ai.location', self.docai_location)
        ICP.set_param('docai_ai.key_path', self.docai_key_path)
        ICP.set_param('docai_ai.invoice_processor_id', self.docai_invoice_processor_id)
        ICP.set_param('docai_ai.receipt_processor_id', self.docai_receipt_processor_id)
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
            docai_receipt_processor_id=ICP.get_param('docai_ai.receipt_processor_id'),
            docai_test_invoice_path=ICP.get_param('docai_ai.test_invoice_path'),
        )
        return res

    def action_test_docai_connection(self):
        """Teste la connexion et l’analyse d’une facture de test avec Google Document AI"""
        ICP = self.env['ir.config_parameter'].sudo()
        project_id = ICP.get_param('docai_ai.project_id')
        location = ICP.get_param('docai_ai.location', 'eu')
        key_path = ICP.get_param('docai_ai.key_path')
        processor_id = ICP.get_param('docai_ai.invoice_processor_id')
        test_invoice_path = ICP.get_param('docai_ai.test_invoice_path')

        if not all([project_id, location, key_path, processor_id, test_invoice_path]):
            raise UserError("⚠️ Remplis tous les champs DocAI + chemin facture test avant de lancer le test.")

        if documentai is None:
            raise UserError("⚠️ Le package google-cloud-documentai n’est pas installé. Fais : pip install google-cloud-documentai")

        if not os.path.exists(test_invoice_path):
            raise UserError(f"⚠️ Facture de test introuvable : {test_invoice_path}")

        try:
            client = documentai.DocumentProcessorServiceClient.from_service_account_json(key_path)
            name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

            with open(test_invoice_path, "rb") as f:
                raw_document = documentai.RawDocument(content=f.read(), mime_type="application/pdf")

            request = documentai.ProcessRequest(name=name, raw_document=raw_document)
            result = client.process_document(request=request)

            # On récupère juste un extrait du texte
            doc_text = result.document.text[:200] if result.document.text else "⚠️ Pas de texte extrait"
            _logger.info("✅ DocAI Test réussi. Extrait : %s", doc_text)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': "Test OK ✅",
                    'message': f"Connexion réussie 🎉 Facture test analysée.\nExtrait : {doc_text}",
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error("❌ Erreur DocAI Test : %s", e, exc_info=True)
            raise UserError(f"❌ Échec de connexion à Document AI : {e}")
