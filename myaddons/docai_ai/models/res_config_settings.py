# -*- coding: utf-8 -*-
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Config Google Cloud (commune aux deux processors)
    docai_project_id = fields.Char("Google Project ID")
    docai_location = fields.Selection(
        [('eu', 'Europe'), ('us', 'USA')],
        default="eu",
        string="DocAI Location"
    )
    docai_key_path = fields.Char("Chemin clé JSON Google")

    # Processors spécifiques
    docai_invoice_processor_id = fields.Char("DocAI Processor ID (Factures)")
    docai_receipt_processor_id = fields.Char("DocAI Processor ID (Reçus)")

    def set_values(self):
        res = super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('docai_ai.project_id', self.docai_project_id)
        ICP.set_param('docai_ai.location', self.docai_location)
        ICP.set_param('docai_ai.key_path', self.docai_key_path)
        ICP.set_param('docai_ai.invoice_processor_id', self.docai_invoice_processor_id)
        ICP.set_param('docai_ai.receipt_processor_id', self.docai_receipt_processor_id)
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
        )
        return res
