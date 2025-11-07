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
    docai_expense_processor_id = fields.Char("Processor Ticket de caisse")
    docai_test_invoice_path = fields.Char("Facture de test")
    docai_test_expense_path = fields.Char("Ticket de caisse de test")

    # Fournisseur / Produit inconnus
    unknown_supplier_id = fields.Many2one("res.partner", string="Fournisseur inconnu")
    unknown_product_id = fields.Many2one("product.product", string="Produit inconnu")

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        res.update(
            unknown_supplier_id=int(ICP.get_param("docai_ai.unknown_supplier_id", 0)) or False,
            unknown_product_id=int(ICP.get_param("docai_ai.unknown_product_id", 0)) or False,
            docai_project_id=ICP.get_param("docai_ai.project_id", ""),
            docai_project_id=ICP.get_param("docai_ai.project_id", ""),
            docai_location=ICP.get_param("docai_ai.location", "eu"),
            docai_key_path=ICP.get_param("docai_ai.key_path", ""),
            docai_invoice_processor_id=ICP.get_param("docai_ai.invoice_processor_id", ""),
            docai_expense_processor_id=ICP.get_param("docai_ai.expense_processor_id", ""),
            docai_test_invoice_path=ICP.get_param("docai_ai.test_invoice_path", ""),
            docai_test_expense_path=ICP.get_param("docai_ai.test_expense_path", ""),
        )
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("docai_ai.project_id", self.docai_project_id or "")
        ICP.set_param("docai_ai.location", self.docai_location or "eu")
        ICP.set_param("docai_ai.key_path", self.docai_key_path or "")
        ICP.set_param("docai_ai.invoice_processor_id", self.docai_invoice_processor_id or "")
        ICP.set_param("docai_ai.expense_processor_id", self.docai_expense_processor_id or "")
        ICP.set_param("docai_ai.test_invoice_path", self.docai_test_invoice_path or "")
        ICP.set_param("docai_ai.test_expense_path", self.docai_test_expense_path or "")

        # Auto-create defaults if missing
        partner = self.unknown_supplier_id or self.env["res.partner"].search([("name", "=", "Fournisseur Inconnu")], limit=1)
        if not partner:
            partner = self.env["res.partner"].create({"name": "Fournisseur Inconnu", "supplier_rank": 1})
        self.unknown_supplier_id = partner
        ICP.set_param("docai_ai.unknown_supplier_id", partner.id)

        product = self.unknown_product_id or self.env["product.product"].search([("name", "=", "Produit Inconnu")], limit=1)
        if not product:
            product = self.env["product.product"].create({"name": "Produit Inconnu", "type": "service"})
        self.unknown_product_id = product
        ICP.set_param("docai_ai.unknown_product_id", product.id)

    def _docai_test_connection(self, processor_id, test_file, label="Document AI"):
        project_id = (self.docai_project_id or "").strip()
        location = (self.docai_location or "eu").strip()
        key_path = (self.docai_key_path or "").strip()

        name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

        try:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

            client = documentai.DocumentProcessorServiceClient(
                client_options={"api_endpoint": f"{location}-documentai.googleapis.com"}
            )

            with open(test_file, "rb") as f:
                file_content = f.read()

            raw_document = documentai.RawDocument(content=file_content, mime_type="application/pdf")
            request = documentai.ProcessRequest(name=name, raw_document=raw_document)
            result = client.process_document(request=request)

            document = result.document
            sample_text = document.text[:300].replace("\n", " ")

            msg = _("✅ Connexion réussie à %s !\nExtrait : %s") % (label, sample_text)
            _logger.info(msg)

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Test %s" % label),
                    "message": msg,
                    "sticky": False,
                    "type": "success",
                },
            }

        except Exception as e:
            msg = _("❌ Erreur connexion %s : %s") % (label, str(e))
            _logger.error(msg)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Test %s" % label),
                    "message": msg,
                    "sticky": True,
                    "type": "danger",
                },
            }

    def action_test_docai_invoice(self):
        self.ensure_one()
        return self._docai_test_connection(
            self.docai_invoice_processor_id,
            self.docai_test_invoice_path,
            label="Document AI (Facture)",
        )

    def action_test_docai_expense(self):
        self.ensure_one()
        return self._docai_test_connection(
            self.docai_expense_processor_id,
            self.docai_test_expense_path,
            label="Document AI (Ticket de caisse)",
        )
