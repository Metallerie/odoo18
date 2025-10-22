# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    docai_json = fields.Text("Document AI JSON brut")

    def action_docai_scan_json(self):
        """Analyse le JSON stocké en base, crée ou met à jour le fournisseur,
        puis met à jour la facture (en brouillon si nécessaire)."""

        for move in self:
            if not move.docai_json:
                raise UserError("Aucun JSON Document AI trouvé sur cette facture.")

            # Charger JSON
            try:
                ent_map = json.loads(move.docai_json)
            except Exception as e:
                raise UserError(f"JSON invalide : {e}")

            _logger.info("🔎 Facture %s → lecture JSON…", move.name)

            # --- Fournisseur ---

            partner = self.env["res.partner"].search(
                [("name", "ilike", supplier_name)], limit=1
            )

            if partner:
                _logger.info("✅ Fournisseur trouvé : %s", partner.name)
                # Mise à jour des infos
                vals = {}
                if ent_map.get("supplier_website"):
                    vals["website"] = ent_map["supplier_website"]
                if ent_map.get("supplier_registration"):
                    vals["company_registry"] = ent_map["supplier_registration"]
                if ent_map.get("supplier_iban"):
                    vals["iban"] = ent_map["supplier_iban"]
                if ent_map.get("supplier_tax_id"):
                    vals["vat"] = ent_map["supplier_tax_id"]
                if ent_map.get("supplier_address"):
                    vals["street"] = ent_map["supplier_address"]
                if vals:
                    partner.write(vals)
            else:
                _logger.info("➕ Création nouveau fournisseur : %s", supplier_name)
                partner = self.env["res.partner"].create({
                    "name": supplier_name,
                    "website": ent_map.get("supplier_website"),
                    "company_registry": ent_map.get("supplier_registration"),
                    "iban": ent_map.get("supplier_iban"),
                    "vat": ent_map.get("supplier_tax_id"),
                    "street": ent_map.get("supplier_address"),
                    "supplier_rank": 1,
                })

            move.partner_id = partner.id

            # --- Gestion de l'état ---
            if move.state == "posted":
                _logger.warning("⚠️ Facture postée → remise en brouillon forcée")
                move.button_draft()

            # --- Nettoyage lignes ---
            move.invoice_line_ids.unlink()

            # --- Mise à jour entête facture ---
            vals_update = {}
            if ent_map.get("invoice_id"):
                vals_update["ref"] = ent_map["invoice_id"]

            if ent_map.get("invoice_date"):
                try:
                    # convertit jj/mm/aaaa → aaaa-mm-jj
                    d, m, y = ent_map["invoice_date"].split("/")
                    vals_update["invoice_date"] = f"{y}-{m}-{d}"
                except Exception:
                    _logger.warning("⚠️ Date facture illisible : %s", ent_map["invoice_date"])

            if vals_update:
                vals_update["is_manually_modified"] = True
                move.write(vals_update)
                _logger.info("✅ Facture mise à jour avec %s", vals_update)

            # --- Taxe (exemple simplifié) ---
            tax_val = None
            vat = ent_map.get("vat")
            if vat:
                vat_clean = vat.replace("%", "").replace(",", ".").strip()
                try:
                    percent = float(vat_clean)
                    tax_val = self.env["account.tax"].search([("amount", "=", percent)], limit=1)
                except Exception:
                    _logger.warning("⚠️ Impossible de parser la TVA : %s", vat)

            # --- Lignes ---
            line_items = ent_map.get("line_items") or []
            if not line_items and ent_map.get("line_item"):
                line_items = [ent_map["line_item"]]

            new_lines = []
            for raw in line_items:
                if isinstance(raw, str):
                    desc = raw
                    qty, price, total = 1, 0, 0
                else:
                    desc = raw.get("description") or raw.get("product_code") or "Ligne"
                    qty = float(raw.get("quantity") or 1)
                    price = float(raw.get("unit_price") or 0)
                    total = float(raw.get("amount") or qty * price)

                vals_line = {
                    "move_id": move.id,
                    "name": desc,
                    "quantity": qty,
                    "price_unit": price,
                }
                if tax_val:
                    vals_line["tax_ids"] = [(6, 0, tax_val.ids)]
                new_lines.append((0, 0, vals_line))

            if new_lines:
                move.write({"invoice_line_ids": new_lines})
                _logger.info("✅ %s lignes importées pour facture %s", len(new_lines), move.name)

            # --- Revalider facture si besoin ---
            if move.state == "draft":
                try:
                    move.action_post()
                    _logger.info("📌 Facture %s validée automatiquement", move.name)
                except Exception as e:
                    _logger.warning("⚠️ Impossible de valider facture %s : %s", move.name, e)
