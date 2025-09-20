import base64
import json
import logging
import os
import re
import requests

from odoo import models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    mindee_local_response = fields.Text(string="Réponse OCR JSON (Mindee)", readonly=True, store=True)

    def _normalize_date(self, date_str):
        """Accepte plusieurs formats de date (04-07-2025, 04/07/2025, 2025-07-04, etc.)"""
        if not date_str:
            return None
        # Uniformiser séparateurs
        date_str = date_str.replace("-", "/").replace(".", "/")
        for fmt in ("%d/%m/%Y", "%Y/%m/%d", "%d/%m/%y"):
            try:
                return fields.Date.to_date(date_str, fmt)
            except Exception:
                continue
        return None

    def _apply_partner_rules(self, ocr_data):
        """Applique les règles OCR pour trouver le fournisseur"""
        PartnerRule = self.env["ocr.configuration.rule.partner"]
        rules = PartnerRule.search([("active", "=", True)], order="sequence asc")

        raw_text = ocr_data.get("raw_text", "").lower()
        partner_name = ocr_data.get("fields", {}).get("supplier_name", "") or ""
        invoice_number = ocr_data.get("fields", {}).get("invoice_number", "") or ""

        for rule in rules:
            if rule.search_in == "raw_text" and rule.keyword.lower() in raw_text:
                return rule.partner_id
            if rule.search_in == "partner_name" and rule.keyword.lower() in partner_name.lower():
                return rule.partner_id
            if rule.search_in == "invoice_number" and rule.keyword.lower() in invoice_number.lower():
                return rule.partner_id
        return None

    def action_ocr_fetch(self):
        for move in self:
            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = pdf_attachments[0]

            file_path = "/tmp/ocr_temp_file.pdf"
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(attachment.datas))

            try:
                response = requests.post(
                    "http://127.0.0.1:1998/ocr",
                    files={"file": open(file_path, "rb")},
                    timeout=30,
                )
                response.raise_for_status()
                result = response.json()
            except Exception as e:
                _logger.error("Mindee v2 erreur pour %s: %s", attachment.name, str(e))
                raise UserError(f"Erreur OCR : {e}")

            # Sauvegarde du JSON OCR
            move.mindee_local_response = json.dumps(result, indent=2, ensure_ascii=False)

            self.env["ir.attachment"].create({
                "name": f"OCR_{attachment.name}.json",
                "res_model": "account.move",
                "res_id": move.id,
                "type": "binary",
                "mimetype": "application/json",
                "datas": base64.b64encode(json.dumps(result, indent=2).encode("utf-8")),
            })

            fields_map = result.get("data", {}).get("fields", {})

            vals = {
                "invoice_date": self._normalize_date(fields_map.get("date")),
                "invoice_date_due": self._normalize_date(fields_map.get("due_date")),
                "invoice_origin": fields_map.get("invoice_number"),
                "amount_untaxed": fields_map.get("total_net"),
                "amount_tax": fields_map.get("total_tax"),
                "amount_total": fields_map.get("total_amount"),
            }

            # Appliquer les règles partenaires
            partner = self._apply_partner_rules(result.get("data", {}))
            if partner:
                vals["partner_id"] = partner.id
                _logger.info("Partenaire assigné via règles OCR : %s", partner.name)
            elif fields_map.get("supplier_name"):
                # fallback → créer un partenaire si inexistant
                partner = self.env["res.partner"].search([("name", "ilike", fields_map["supplier_name"])], limit=1)
                if not partner:
                    partner = self.env["res.partner"].create({
                        "name": fields_map["supplier_name"],
                        "supplier_rank": 1,
                    })
                vals["partner_id"] = partner.id
                _logger.info("Partenaire assigné via supplier_name OCR : %s", partner.name)
            else:
                _logger.warning("Aucun partenaire détecté pour la facture %s", move.name)

            move.write(vals)

        return True
