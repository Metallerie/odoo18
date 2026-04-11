# -*- coding: utf-8 -*-

import json
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    # -------------------------------------------------------------------------
    # OUTILS
    # -------------------------------------------------------------------------
    def _docai_normalize_text(self, value):
        if not value:
            return ""

        value = str(value).lower().strip()

        for char in ['"', "'", "\n", "\r", "\t", ",", ";", ":", ".", "(", ")", "-", "_", "/", "\\", "[", "]", "{", "}"]:
            value = value.replace(char, " ")

        return " ".join(value.split())

    def _docai_get_line_items(self, data):
        self.ensure_one()
        line_items = data.get("line_items", [])
        return line_items if isinstance(line_items, list) else []

    def _docai_get_item_values(self, item):
        """
        Normalise les clés possibles d'un line_item.
        """
        return {
            "product_code": (
                item.get("product_code")
                or item.get("item_code")
                or item.get("reference")
                or item.get("default_code")
                or ""
            ).strip(),
            "description": (
                item.get("description")
                or item.get("name")
                or item.get("product_name")
                or item.get("label")
                or ""
            ).strip(),
            "quantity": item.get("quantity") or 0,
            "unit_price": item.get("unit_price") or 0,
            "amount": item.get("amount") or item.get("total") or 0,
        }

    def _docai_to_float(self, value, default=0.0):
        if value in (False, None, ""):
            return default
        try:
            if isinstance(value, str):
                value = value.replace("€", "").replace(" ", "").replace(",", ".")
            return float(value)
        except Exception:
            return default

    # -------------------------------------------------------------------------
    # RECHERCHE ALLER : REFERENCE
    # -------------------------------------------------------------------------
    def _docai_find_product_by_reference(self, item_vals):
        self.ensure_one()
        Product = self.env["product.product"].sudo()

        product_code = (item_vals.get("product_code") or "").strip()
        if not product_code:
            return False

        product = Product.search([("default_code", "=", product_code)], limit=1)
        if product:
            _logger.info("[DocAI] Produit trouvé par référence exacte pour move %s : %s", self.id, product.display_name)
            return product

        product = Product.search([("barcode", "=", product_code)], limit=1)
        if product:
            _logger.info("[DocAI] Produit trouvé par barcode exact pour move %s : %s", self.id, product.display_name)
            return product

        product = Product.search([("default_code", "ilike", product_code)], limit=1)
        if product:
            _logger.info("[DocAI] Produit trouvé par référence approchée pour move %s : %s", self.id, product.display_name)
            return product

        return False

    # -------------------------------------------------------------------------
    # RECHERCHE ALLER : NOM
    # -------------------------------------------------------------------------
    def _docai_find_product_by_name(self, item_vals):
        self.ensure_one()
        Product = self.env["product.product"].sudo()

        description = (item_vals.get("description") or "").strip()
        if not description:
            return False

        product = Product.search([("name", "ilike", description)], limit=1)
        if product:
            _logger.info("[DocAI] Produit trouvé par nom direct pour move %s : %s", self.id, product.display_name)
            return product

        return False

    # -------------------------------------------------------------------------
    # RECHERCHE INVERSE
    # -------------------------------------------------------------------------
    def _docai_find_product_by_reverse_search(self, item_vals):
        self.ensure_one()
        Product = self.env["product.product"].sudo()

        item_text = self._docai_normalize_text(json.dumps(item_vals, ensure_ascii=False))
        if not item_text:
            return False

        products = Product.search([("active", "=", True)])

        exact_matches = []
        partial_matches = []

        for product in products:
            default_code = self._docai_normalize_text(product.default_code or "")
            name = self._docai_normalize_text(product.name or "")

            if default_code and len(default_code) >= 3 and default_code in item_text:
                exact_matches.append(product)
                continue

            if name and len(name) >= 4 and name in item_text:
                exact_matches.append(product)
                continue

            name_words = [w for w in name.split() if len(w) >= 4]
            if name_words and all(word in item_text for word in name_words):
                partial_matches.append(product)

        if exact_matches:
            if len(exact_matches) > 1:
                _logger.warning(
                    "[DocAI] Plusieurs produits trouvés en recherche inverse exacte pour move %s : %s",
                    self.id,
                    ", ".join(exact_matches.mapped("display_name")),
                )
            return exact_matches[0]

        if partial_matches:
            if len(partial_matches) > 1:
                _logger.warning(
                    "[DocAI] Plusieurs produits trouvés en recherche inverse partielle pour move %s : %s",
                    self.id,
                    ", ".join(partial_matches.mapped("display_name")),
                )
            return partial_matches[0]

        return False

    # -------------------------------------------------------------------------
    # RECHERCHE COMPLETE D'UN PRODUIT
    # -------------------------------------------------------------------------
    def _docai_find_product_from_item(self, item):
        self.ensure_one()

        item_vals = self._docai_get_item_values(item)
        product = False

        product = self._docai_find_product_by_reference(item_vals)

        if not product:
            product = self._docai_find_product_by_name(item_vals)

        if not product:
            product = self._docai_find_product_by_reverse_search(item_vals)

        if not product:
            _logger.warning(
                "[DocAI] Aucun produit trouvé pour move %s | code=%s | description=%s",
                self.id,
                item_vals.get("product_code"),
                item_vals.get("description"),
            )

        return product, item_vals

    # -------------------------------------------------------------------------
    # PREPARATION DES LIGNES
    # -------------------------------------------------------------------------
    def _docai_prepare_invoice_line_vals(self, product, item_vals):
        self.ensure_one()

        qty = self._docai_to_float(item_vals.get("quantity"), default=1.0)
        price_unit = self._docai_to_float(item_vals.get("unit_price"), default=0.0)
        amount = self._docai_to_float(item_vals.get("amount"), default=0.0)

        if qty <= 0:
            qty = 1.0

        if price_unit == 0.0 and amount and qty:
            price_unit = amount / qty

        name = item_vals.get("description") or product.display_name

        return {
            "move_id": self.id,
            "product_id": product.id,
            "name": name,
            "quantity": qty,
            "price_unit": price_unit,
        }

    def _docai_prepare_note_line_vals(self, item_vals):
        self.ensure_one()

        code = item_vals.get("product_code") or ""
        description = item_vals.get("description") or "Produit non identifié"
        qty = item_vals.get("quantity") or ""
        unit_price = item_vals.get("unit_price") or ""
        amount = item_vals.get("amount") or ""

        note = (
            f"[DocAI - produit non trouvé] "
            f"Réf: {code} | Désignation: {description} | "
            f"Qté: {qty} | PU: {unit_price} | Montant: {amount}"
        )

        return {
            "move_id": self.id,
            "display_type": "line_note",
            "name": note,
        }

    def _docai_clear_existing_lines(self):
        """
        Supprime les lignes existantes non section/note avant reconstruction.
        Garde les notes/sections manuelles.
        """
        self.ensure_one()

        product_lines = self.invoice_line_ids.filtered(lambda l: not l.display_type)
        if product_lines:
            product_lines.unlink()

    # -------------------------------------------------------------------------
    # TRAITEMENT DES LIGNES
    # -------------------------------------------------------------------------
    def _docai_process_line_items(self, data):
        self.ensure_one()

        line_items = self._docai_get_line_items(data)
        if not line_items:
            _logger.info("[DocAI] Aucun line_items pour move %s", self.id)
            return

        _logger.info("[DocAI] %s line_items détectés pour move %s", len(line_items), self.id)

        # On repart proprement
        self._docai_clear_existing_lines()

        line_model = self.env["account.move.line"].sudo()

        for item in line_items:
            product, item_vals = self._docai_find_product_from_item(item)

            if product:
                vals = self._docai_prepare_invoice_line_vals(product, item_vals)
                line_model.create(vals)
                _logger.info(
                    "[DocAI] Ligne produit créée pour move %s -> %s",
                    self.id,
                    product.display_name,
                )
            else:
                vals = self._docai_prepare_note_line_vals(item_vals)
                line_model.create(vals)
                _logger.info(
                    "[DocAI] Ligne note créée pour move %s | code=%s | description=%s",
                    self.id,
                    item_vals.get("product_code"),
                    item_vals.get("description"),
                )
