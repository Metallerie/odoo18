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
    # RECHERCHE PRODUIT
    # -------------------------------------------------------------------------
    def _docai_find_product_by_reference(self, item_vals):
        self.ensure_one()
        Product = self.env["product.product"].sudo()

        product_code = (item_vals.get("product_code") or "").strip()
        if not product_code:
            return False

        product = Product.search([("default_code", "=", product_code)], limit=1)
        if product:
            return product

        product = Product.search([("barcode", "=", product_code)], limit=1)
        if product:
            return product

        product = Product.search([("default_code", "ilike", product_code)], limit=1)
        if product:
            return product

        return False

    def _docai_find_product_by_name(self, item_vals):
        self.ensure_one()
        Product = self.env["product.product"].sudo()

        description = (item_vals.get("description") or "").strip()
        if not description:
            return False

        product = Product.search([("name", "ilike", description)], limit=1)
        return product or False

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
            return exact_matches[0]

        if partial_matches:
            return partial_matches[0]

        return False

    def _docai_find_product_from_item(self, item):
        self.ensure_one()

        item_vals = self._docai_get_item_values(item)
        product = False

        product = self._docai_find_product_by_reference(item_vals)

        if not product:
            product = self._docai_find_product_by_name(item_vals)

        if not product:
            product = self._docai_find_product_by_reverse_search(item_vals)

        return product, item_vals

    # -------------------------------------------------------------------------
    # CATEGORIE / CREATION PRODUIT
    # -------------------------------------------------------------------------
    def _docai_get_or_create_unvalidated_category(self):
        self.ensure_one()
        Category = self.env["product.category"].sudo()

        parent = Category.search([("name", "=", "DocAI")], limit=1)
        if not parent:
            parent = Category.create({"name": "DocAI"})

        category = Category.search([
            ("name", "=", "Non validés"),
            ("parent_id", "=", parent.id),
        ], limit=1)

        if not category:
            category = Category.create({
                "name": "Non validés",
                "parent_id": parent.id,
            })

        return category

    def _docai_item_has_minimum_data_for_product_creation(self, item_vals):
        self.ensure_one()

        has_ref_or_name = bool(
            (item_vals.get("product_code") or "").strip()
            or (item_vals.get("description") or "").strip()
        )

        qty = self._docai_to_float(item_vals.get("quantity"), default=0.0)
        unit_price = self._docai_to_float(item_vals.get("unit_price"), default=0.0)
        amount = self._docai_to_float(item_vals.get("amount"), default=0.0)

        return bool(
            has_ref_or_name
            and qty > 0
            and unit_price > 0
            and amount > 0
        )

    def _docai_create_unvalidated_product(self, item_vals):
        self.ensure_one()
        Product = self.env["product.product"].sudo()

        category = self._docai_get_or_create_unvalidated_category()

        product_code = (item_vals.get("product_code") or "").strip()
        description = (item_vals.get("description") or "").strip()

        product_name = description or product_code or "Produit DocAI non validé"

        existing = False
        if product_code:
            existing = Product.search([("default_code", "=", product_code)], limit=1)

        if not existing and description:
            existing = Product.search([
                ("name", "=", product_name),
                ("categ_id", "=", category.id),
            ], limit=1)

        if existing:
            _logger.info(
                "[DocAI] Produit non validé déjà existant pour move %s : %s",
                self.id,
                existing.display_name,
            )
            return existing

        vals = {
            "name": product_name,
            "default_code": product_code or False,
            "categ_id": category.id,
            "purchase_ok": True,
            "sale_ok": False,
        }

        product = Product.create(vals)

        _logger.warning(
            "[DocAI] Produit créé dans DocAI / Non validés pour move %s : %s",
            self.id,
            product.display_name,
        )

        return product

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
            f"[DocAI - données incomplètes] "
            f"Réf: {code} | Désignation: {description} | "
            f"Qté: {qty} | PU: {unit_price} | Montant: {amount}"
        )

        return {
            "move_id": self.id,
            "display_type": "line_note",
            "name": note,
        }

    def _docai_clear_existing_lines(self):
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

        self._docai_clear_existing_lines()

        line_model = self.env["account.move.line"].sudo()

        for item in line_items:
            product, item_vals = self._docai_find_product_from_item(item)

            if not product:
                if self._docai_item_has_minimum_data_for_product_creation(item_vals):
                    product = self._docai_create_unvalidated_product(item_vals)

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
                    "[DocAI] Ligne commentaire créée pour move %s | code=%s | description=%s",
                    self.id,
                    item_vals.get("product_code"),
                    item_vals.get("description"),
                )
