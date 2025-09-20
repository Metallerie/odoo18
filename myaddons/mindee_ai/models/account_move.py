import base64
import json
import logging
import os
import requests
from datetime import datetime

from odoo import models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    mindee_local_response = fields.Text(
        string="Réponse OCR JSON (Mindee)",
        readonly=True,
        store=True
    )

    # --- Normalisation des dates ---
    def _normalize_date(self, date_str):
        """Convertit une date OCR en format YYYY-MM-DD utilisable par Odoo."""
        if not date_str:
            return None
        date_str = date_str.strip().replace("-", "/").replace(".", "/")
        for fmt in ("%d/%m/%Y", "%Y/%m/%d", "%d/%m/%y"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except Exception:
                continue
        return None

    # --- Application des règles partenaires ---
    def _apply_partner_rules(self, ocr_data):
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

    # --- Action principale OCR ---
    def action_ocr_fetch(self):
        for move in self:
            # On prend uniquement les PDFs
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

            # Sauvegarde JSON brut
            move.mindee_local_response = json.dumps(result, indent=2, ensure_ascii=False)

            # Création d'une pièce jointe JSON
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
                "ref": fields_map.get("invoice_number"),   # ✅ Numéro de facture fournisseur
                "amount_untaxed": fields_map.get("total_net"),
                "amount_tax": fields_map.get("total_tax"),
                "amount_total": fields_map.get("total_amount"),
            }

            # Attribution du partenaire via règles OCR
            partner = self._apply_partner_rules(result.get("data", {}))
            if partner:
                vals["partner_id"] = partner.id
                _logger.info("Partenaire assigné via règles OCR : %s", partner.name)
            elif fields_map.get("supplier_name"):
                # Fallback : création/recherche par supplier_name
                supplier_name = fields_map["supplier_name"]
                partner = self.env["res.partner"].search([("name", "ilike", supplier_name)], limit=1)
                if not partner:
                    partner = self.env["res.partner"].create({
                        "name": supplier_name,
                        "supplier_rank": 1,
                    })
                vals["partner_id"] = partner.id
                _logger.info("Partenaire assigné via supplier_name OCR : %s", partner.name)
            else:
                _logger.warning("Aucun partenaire détecté pour la facture %s", move.name)

            # Mise à jour de la facture
            try:
                move.write(vals)
                _logger.info("Facture %s mise à jour avec les données OCR", move.name)
            except Exception as e:
                _logger.error("Erreur d’écriture dans la facture %s : %s", move.name, str(e))
                raise UserError(f"Erreur d’écriture dans la facture : {e}")

        return True
