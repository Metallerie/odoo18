# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_docai_scan_json(self):
        """
        Lit le champ docai_json (Document AI) et met à jour la facture
        + ses lignes (account.move.line).
        """
        for move in self:
            if not move.docai_json:
                raise UserError(_("Aucun JSON DocAI trouvé sur cette facture."))

            try:
                data = json.loads(move.docai_json)
                entities = {
                    ent.get("type_"): ent.get("mentionText")
                    for ent in data.get("entities", [])
                }

                vals = {}
                # Numéro de facture
                if "invoice_id" in entities:
                    vals["ref"] = entities["invoice_id"]

                # Date de facture
                if "invoice_date" in entities:
                    vals["invoice_date"] = entities["invoice_date"]

                # Fournisseur
                partner = None
                if "supplier_registration" in entities:
                    partner = self.env["res.partner"].search([
                        ("vat", "=", entities["supplier_registration"])
                    ], limit=1)
                if not partner and "supplier_name" in entities:
                    partner = self.env["res.partner"].search([
                        ("name", "ilike", entities["supplier_name"])
                    ], limit=1)
                if partner:
                    vals["partner_id"] = partner.id

                # Totaux
                if "total_amount" in entities:
                    try:
                        vals["amount_total"] = float(entities["total_amount"].replace(",", "."))
                    except Exception:
                        _logger.warning(f"Impossible de parser total_amount {entities['total_amount']}")

                # Appliquer les infos simples
                if vals:
                    move.write(vals)

                # 🧾 Lignes de facture
                line_items = [ent for ent in data.get("entities", []) if ent.get("type_") == "line_item"]

                if line_items:
                    move.line_ids.unlink()  # ⚠️ on supprime les anciennes lignes

                    new_lines = []
                    for item in line_items:
                        description = item.get("mentionText") or "Ligne"
                        quantity = 1.0
                        price_unit = 0.0
                        total = 0.0

                        for prop in item.get("properties", []):
                            if prop.get("type_") in ["item_description", "description"]:
                                description = prop.get("mentionText")
                            elif prop.get("type_") in ["quantity"]:
                                try:
                                    quantity = float(prop.get("mentionText").replace(",", "."))
                                except Exception:
                                    pass
                            elif prop.get("type_") in ["unit_price", "price"]:
                                try:
                                    price_unit = float(prop.get("mentionText").replace(",", "."))
                                except Exception:
                                    pass
                            elif prop.get("type_") in ["amount", "total_amount", "line_total"]:
                                try:
                                    total = float(prop.get("mentionText").replace(",", "."))
                                except Exception:
                                    pass

                        new_lines.append((0, 0, {
                            "name": description,
                            "quantity": quantity,
                            "price_unit": price_unit or total,
                            "account_id": move.journal_id.default_account_id.id,
                        }))

                    if new_lines:
                        move.write({"invoice_line_ids": new_lines})
                        _logger.info(f"✅ Facture {move.id} lignes mises à jour depuis JSON ({len(new_lines)} lignes)")

                else:
                    _logger.warning(f"⚠️ Facture {move.id} : aucune ligne trouvée dans JSON")

            except Exception as e:
                _logger.error(f"❌ Erreur parsing JSON DocAI facture {move.id} : {e}")
                raise UserError(_("Erreur parsing JSON : %s") % e)
