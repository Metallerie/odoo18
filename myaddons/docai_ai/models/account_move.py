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
        Lit le champ docai_json (JSON simplifié DocAI)
        et met à jour les infos de la facture + lignes
        """
        for move in self:
            if not move.docai_json:
                raise UserError(_("Aucun JSON DocAI trouvé sur cette facture."))

            try:
                data = json.loads(move.docai_json)
                vals = {}

                # Champs simples
                if data.get("invoice_id"):
                    vals["ref"] = data["invoice_id"]

                if data.get("invoice_date"):
                    vals["invoice_date"] = data["invoice_date"]

                if data.get("supplier_name"):
                    partner = self.env["res.partner"].search([
                        ("name", "ilike", data["supplier_name"])
                    ], limit=1)
                    if partner:
                        vals["partner_id"] = partner.id

                if data.get("total_amount"):
                    try:
                        vals["amount_total"] = float(data["total_amount"])
                    except Exception:
                        _logger.warning(f"⚠️ Montant invalide dans JSON facture {move.id}: {data.get('total_amount')}")

                # Appliquer les champs simples
                if vals:
                    move.write(vals)
                    _logger.info(f"✅ Facture {move.id} mise à jour depuis JSON simplifié : {vals}")

                # Traitement des lignes
                if "line_item" in data and data["line_item"]:
                    lines = []
                    for item in data["line_item"]:
                        product = self.env["product.product"].search([
                            ("name", "ilike", item.get("description", ""))
                        ], limit=1)

                        line_vals = {
                            "name": item.get("description", "Ligne importée"),
                            "quantity": float(item.get("quantity") or 1.0),
                            "price_unit": float(item.get("unit_price") or 0.0),
                            "move_id": move.id,
                        }
                        if product:
                            line_vals["product_id"] = product.id

                        lines.append((0, 0, line_vals))

                    if lines:
                        move.write({"invoice_line_ids": lines})
                        _logger.info(f"✅ {len(lines)} lignes ajoutées depuis JSON simplifié pour facture {move.id}")
                    else:
                        _logger.warning(f"⚠️ Facture {move.id} : aucune ligne trouvée dans JSON simplifié")

            except Exception as e:
                _logger.error(f"❌ Erreur parsing JSON DocAI facture {move.id} : {e}")
                raise UserError(_("Erreur parsing JSON : %s") % e)

    # -------------------------------------------------------------------------
    # Bouton Debug JSON
    # -------------------------------------------------------------------------
    def action_docai_debug_json(self):
        """
        Debug : affiche les clés principales du JSON simplifié
        """
        for move in self:
            if not move.docai_json:
                raise UserError(_("Aucun JSON DocAI trouvé sur cette facture."))

            try:
                data = json.loads(move.docai_json)
                top_keys = list(data.keys())
                _logger.info(f"🔍 Facture {move.id} - clés JSON : {top_keys}")
                raise UserError(_("Clés JSON détectées : %s") % ", ".join(top_keys))
            except Exception as e:
                raise UserError(_("Erreur parsing JSON : %s") % e)
