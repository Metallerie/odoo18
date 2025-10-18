# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    def action_docai_scan_attachment(self):
        """
        Bouton qui lit la première pièce jointe PDF liée à la facture,
        parse le champ docai_response_json et met à jour la facture.
        """
        for move in self:
            attachment = self.env["ir.attachment"].search([
                ("res_model", "=", "account.move"),
                ("res_id", "=", move.id),
                ("mimetype", "=", "application/pdf"),
                ("docai_response_json", "!=", False),
            ], limit=1)

            if not attachment:
                _logger.warning(f"[DocAI] Aucune pièce jointe DocAI trouvée pour facture {move.id}")
                continue

            try:
                response = json.loads(attachment.docai_response_json)
            except Exception as e:
                _logger.error(f"[DocAI] Erreur parsing JSON : {e}")
                continue

            # Exemple d’extraction simple
            entities = response.get("document", {}).get("entities", [])
            values = {e.get("type"): e.get("mentionText") for e in entities}

            supplier_name = values.get("supplier_name")
            invoice_id = values.get("invoice_id")
            total_amount = values.get("total_amount")

            _logger.info(f"[DocAI] Facture {move.id} -> Fournisseur={supplier_name}, N°={invoice_id}, Total={total_amount}")

            # TODO : map vers les bons champs Odoo (res.partner, amount_total, etc.)
            if invoice_id:
                move.ref = invoice_id
            if total_amount:
                move.amount_total = float(total_amount.replace(",", "."))
            if supplier_name:
                partner = self.env["res.partner"].search([("name", "ilike", supplier_name)], limit=1)
                if partner:
                    move.partner_id = partner.id

        return True
