# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    # -------------------------------------------------------------------------
    # Action principale : lecture du JSON brut Document AI
    # -------------------------------------------------------------------------
    def action_docai_scan_json(self):
        """
        Lit le champ docai_json (JSON brut DocAI avec entities/properties)
        et met à jour les infos de la facture + lignes
        """
        for move in self:
            if not move.docai_json:
                raise UserError(_("Aucun JSON DocAI trouvé sur cette facture."))

            try:
                data = json.loads(move.docai_json)
                entities = data.get("entities", [])
                vals = {}

                # Mapping des entités simples
                ent_map = {
                    ent.get("type_"): ent.get("mentionText")
                    for ent in entities if ent.get("mentionText")
                }

                # Numéro de facture
                if "invoice_id" in ent_map:
                    vals["ref"] = ent_map["invoice_id"]

                # Date de facture
                if "invoice_date" in ent_map:
                    vals["invoice_date"] = ent_map["invoice_date"]

                # Fournisseur
                if "supplier_name" in ent_map:
                    partner = self.env["res.partner"].search([
                        ("name", "ilike", ent_map["supplier_name"])
                    ], limit=1)
                    if partner:
                        vals["partner_id"] = partner.id

                # Montant total
                if "total_amount" in ent_map:
                    try:
                        vals["amount_total"] = float(ent_map["total_amount"])
                    except Exception:
                        _logger.warning(
                            f"⚠️ Montant invalide pour facture {move.id}: {ent_map['total_amount']}"
                        )

                # Appliquer les modifications simples
                if vals:
                    move.write(vals)
                    _logger.info(f"✅ Facture {move.id} mise à jour depuis JSON brut : {vals}")

                # -----------------------------------------------------------------
                # Traitement des lignes de facture
                # -----------------------------------------------------------------
                lines = []
                for ent in entities:
                    if ent.get("type_") == "line_item":
                        line_data = {
                            prop.get("type_"): prop.get("mentionText")
                            for prop in ent.get("properties", [])
                            if prop.get("mentionText")
                        }

                        line_vals = {
                            "name": line_data.get("description", "Ligne importée"),
                            "quantity": float(line_data.get("quantity") or 1.0),
                            "price_unit": float(line_data.get("unit_price") or 0.0),
                            "move_id": move.id,
                        }

                        # Associer un produit si trouvé
                        product = self.env["product.product"].search([
                            ("name", "ilike", line_data.get("description", ""))
                        ], limit=1)
                        if product:
                            line_vals["product_id"] = product.id

                        lines.append((0, 0, line_vals))

                if lines:
                    move.write({"invoice_line_ids": lines})
                    _logger.info(f"✅ {len(lines)} lignes ajoutées depuis JSON brut pour facture {move.id}")
                else:
                    _logger.warning(f"⚠️ Facture {move.id} : aucune ligne trouvée dans JSON brut")

            except Exception as e:
                _logger.error(f"❌ Erreur parsing JSON DocAI facture {move.id} : {e}")
                raise UserError(_("Erreur parsing JSON : %s") % e)

    # -------------------------------------------------------------------------
    # Action debug : affiche les clés disponibles dans le JSON
    # -------------------------------------------------------------------------
    def action_docai_debug_json(self):
        """
        Debug : affiche les clés principales du JSON brut
        """
        for move in self:
            if not move.docai_json:
                raise UserError(_("Aucun JSON DocAI trouvé sur cette facture."))

            try:
                data = json.loads(move.docai_json)
                keys = list(data.keys())
                _logger.info(f"🔍 Facture {move.id} - clés JSON : {keys}")
                raise UserError(_("Clés JSON détectées : %s") % ", ".join(keys))
            except Exception as e:
                raise UserError(_("Erreur parsing JSON : %s") % e)
