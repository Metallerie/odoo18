# -*- coding: utf-8 -*-

import json
import logging

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
_logger.error("######## account_move.py CHARGÉ ########")


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_docai_scan_json(self):
        for move in self:
            _logger.warning("######## DOCAI BOUTON CLIQUÉ ########")

            source_json = move.docai_json or move.docai_json_raw

            _logger.warning("[DocAI] source_json trouvé = %s", bool(source_json))

            if not source_json:
                raise UserError("Aucun JSON trouvé sur cette facture.")

            try:
                data = json.loads(source_json)
            except Exception as e:
                _logger.error("[DocAI] Erreur lecture JSON : %s", e)
                raise UserError("Impossible de lire le JSON.")

            _logger.warning("[DocAI] invoice_id = %s", data.get("invoice_id"))
            _logger.warning("[DocAI] invoice_date = %s", data.get("invoice_date"))
            _logger.warning("[DocAI] supplier_name = %s", data.get("supplier_name"))

            # =========================
            # Entête facture
            # =========================

            supplier_name = data.get("supplier_name")
            invoice_id = data.get("invoice_id")
            invoice_date = data.get("invoice_date")

            if supplier_name:
                partner = self.env["res.partner"].search(
                    [("name", "ilike", supplier_name)],
                    limit=1
                )

                if partner:
                    _logger.warning("[DocAI] Fournisseur trouvé : %s", partner.name)
                    move.partner_id = partner.id
                else:
                    _logger.warning("[DocAI] Fournisseur inconnu : %s", supplier_name)

            if invoice_id:
                move.ref = invoice_id

            # =========================
            # Lignes facture
            # =========================

            line_items = data.get("line_items") or []
            _logger.warning("[DocAI] Nombre de lignes détectées : %s", len(line_items))

            new_lines = []

            for item in line_items:
                _logger.warning("[DocAI] Ligne brute : %s", item)

                description = (
                    item.get("description")
                    or item.get("name")
                    or item.get("label")
                    or ""
                ).strip()

                code = (
                    item.get("code")
                    or item.get("reference")
                    or item.get("product_code")
                    or ""
                ).strip()

                quantity = float(item.get("quantity") or 1.0)
                price_unit = float(item.get("unit_price") or 0.0)
                amount = float(item.get("amount") or item.get("total_amount") or 0.0)

                _logger.warning(
                    "[DocAI] description=%s code=%s quantity=%s price=%s amount=%s",
                    description,
                    code,
                    quantity,
                    price_unit,
                    amount,
                )

                # Ligne commentaire
                if amount == 0:
                    comment_text = description or code or "Ligne sans montant"

                    new_lines.append((0, 0, {
                        "display_type": "line_note",
                        "name": comment_text,
                    }))

                    _logger.warning("[DocAI] Ligne commentaire créée : %s", comment_text)
                    continue

                # Recherche produit aller
                product = False

                if code:
                    product = self.env["product.product"].search([
                        "|",
                        ("default_code", "=", code),
                        ("barcode", "=", code)
                    ], limit=1)

                    if product:
                        _logger.warning("[DocAI] Produit trouvé par code : %s", product.display_name)

                if not product and description:
                    product = self.env["product.product"].search([
                        ("name", "ilike", description)
                    ], limit=1)

                    if product:
                        _logger.warning("[DocAI] Produit trouvé par nom : %s", product.display_name)

                # Recherche inverse
                if not product and description:
                    words = description.split()
                    domain = []

                    for word in words[:3]:
                        domain.append(("name", "ilike", word))

                    if domain:
                        product = self.env["product.product"].search(domain, limit=1)

                    if product:
                        _logger.warning("[DocAI] Produit trouvé en recherche inverse : %s", product.display_name)

                # Création produit si absent
                if not product:
                    create_name = description or code or "Produit DocAI"

                    product = self.env["product.product"].create({
                        "name": create_name,
                        "default_code": code if code else False,
                        "categ_id": self.env.ref("product.product_category_all").id,
                        "sale_ok": False,
                        "purchase_ok": True,
                    })

                    _logger.warning("[DocAI] Produit créé : %s", product.display_name)

                    # Ligne commentaire
                    new_lines.append((0, 0, {
                        "display_type": "line_note",
                        "name": "Produit créé automatiquement depuis DocAI : %s" % product.display_name,
                    }))

                account_id = (
                    product.property_account_expense_id.id
                    or product.categ_id.property_account_expense_categ_id.id
                )

                if not account_id:
                    raise UserError(
                        "Aucun compte de charge trouvé pour le produit : %s" % product.display_name
                    )

                if not price_unit and quantity and amount:
                    price_unit = amount / quantity

                new_lines.append((0, 0, {
                    "product_id": product.id,
                    "name": description or product.display_name,
                    "quantity": quantity,
                    "price_unit": price_unit,
                    "account_id": account_id,
                }))

                _logger.warning("[DocAI] Ligne produit créée : %s", description)

            if new_lines:
                move.write({
                    "invoice_line_ids": [(5, 0, 0)] + new_lines
                })

                _logger.warning("[DocAI] %s lignes écrites sur la facture", len(new_lines))

            raise UserError("Scan DocAI terminé. Vérifie les logs.")
