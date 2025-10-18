# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, api, fields

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    def action_docai_scan_attachment(self):
        """
        Bouton qui lit la pièce jointe PDF liée à la facture,
        parse docai_response_json et met à jour la facture + lignes.
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

            # Extraction des entités principales
            entities = response.get("document", {}).get("entities", [])
            values = {e.get("type"): e.get("mentionText") for e in entities}

            supplier_name = values.get("supplier_name")
            invoice_id = values.get("invoice_id")
            invoice_date = values.get("invoice_date")
            due_date = values.get("due_date")
            currency = values.get("currency", "EUR")
            total_amount = values.get("total_amount")
            vat_amount = values.get("vat/tax_amount")
            net_amount = values.get("net_amount")

            # === Fournisseur ===
            if supplier_name:
                partner = self.env["res.partner"].search([("name", "ilike", supplier_name)], limit=1)
                if partner:
                    move.partner_id = partner.id

            # === En-tête de facture ===
            if invoice_id:
                move.ref = invoice_id
            if invoice_date:
                move.invoice_date = fields.Date.from_string(invoice_date)
            if due_date:
                move.invoice_date_due = fields.Date.from_string(due_date)

            if currency:
                cur = self.env["res.currency"].search([("name", "=", currency)], limit=1)
                if cur:
                    move.currency_id = cur.id

            # === Totaux ===
            if total_amount:
                try:
                    move.amount_total = float(total_amount.replace(",", "."))
                except Exception:
                    pass

            # === Lignes produits ===
            # Nettoyage des lignes existantes
            move.invoice_line_ids.unlink()

            line_items = [e for e in entities if e.get("type", "").startswith("line_item")]

            current_line = {}
            for e in line_items:
                t = e.get("type")
                v = e.get("mentionText")

                if t.endswith("/description"):
                    current_line["name"] = v
                elif t.endswith("/product_code"):
                    current_line["product_code"] = v
                elif t.endswith("/quantity"):
                    try:
                        current_line["quantity"] = float(v.replace(",", "."))
                    except Exception:
                        current_line["quantity"] = 1.0
                elif t.endswith("/unit_price"):
                    try:
                        current_line["price_unit"] = float(v.replace(",", "."))
                    except Exception:
                        current_line["price_unit"] = 0.0
                elif t.endswith("/amount"):
                    try:
                        current_line["price_subtotal"] = float(v.replace(",", "."))
                    except Exception:
                        pass

                # Quand on a une description ET un montant, on crée la ligne
                if "name" in current_line and "price_unit" in current_line and "quantity" in current_line:
                    move.write({
                        "invoice_line_ids": [(0, 0, {
                            "name": current_line.get("name"),
                            "quantity": current_line.get("quantity", 1.0),
                            "price_unit": current_line.get("price_unit", 0.0),
                            # TODO : map produit si code existe
                        })]
                    })
                    current_line = {}

            _logger.info(f"[DocAI] Facture {move.id} remplie depuis {attachment.name}")

        return True
