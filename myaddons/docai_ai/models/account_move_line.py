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

    def _docai_to_float(self, value, default=0.0):
        if value in (False, None, ""):
            return default
        try:
            if isinstance(value, str):
                value = value.replace("€", "").replace(" ", "").replace(",", ".")
            return float(value)
        except Exception:
            return default

    def _docai_extract_best_amount(self, value):
        """
        Gère :
        - "29,00"
        - ["29,00", "34,80"]
        - 34.80
        """
        if value in (False, None, ""):
            return 0.0

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            return self._docai_to_float(value, default=0.0)

        if isinstance(value, list):
            amounts = []
            for v in value:
                f = self._docai_to_float(v, default=0.0)
                if f > 0:
                    amounts.append(f)
            if not amounts:
                return 0.0
            return max(amounts)

        return 0.0

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
            "mention_text": (item.get("_mentionText") or "").strip(),
            "quantity": item.get("quantity") or 0,
            "unit_price": item.get("unit_price") or 0,
            "amount": item.get("amount") or item.get("total") or 0,
        }

    # -------------------------------------------------------------------------
    # RECHERCHE PRODUIT : REFERENCE / NOM / INVERSE
    # -------------------------------------------------------------------------
    def _docai_find_product_by_reference(self, item_vals):
        self.ensure_one()
        Product = self.env["product.product"].sudo()

        product_code = (item_vals.get("product_code") or "").strip()
        if not product_code:
            return False

        product = Product.search([("default_code", "=", product_code)], limit=1)
        if product:
            _logger.info(
                "[DocAI] Produit trouvé par référence exacte pour move %s : %s",
                self.id,
                product.display_name,
            )
            return product

        product = Product.search([("barcode", "=", product_code)], limit=1)
        if product:
            _logger.info(
                "[DocAI] Produit trouvé par barcode exact pour move %s : %s",
                self.id,
                product.display_name,
            )
            return product

        product = Product.search([("default_code", "ilike", product_code)], limit=1)
        if product:
            _logger.info(
                "[DocAI] Produit trouvé par référence approchée pour move %s : %s",
                self.id,
                product.display_name,
            )
            return product

        return False

    def _docai_find_product_by_name(self, item_vals):
        self.ensure_one()
        Product = self.env["product.product"].sudo()

        description = (item_vals.get("description") or "").strip()
        if not description:
            return False

        product = Product.search([("name", "=", description)], limit=1)
        if product:
            _logger.info(
                "[DocAI] Produit trouvé par nom exact pour move %s : %s",
                self.id,
                product.display_name,
            )
            return product

        normalized_description = self._docai_normalize_text(description)
        products = Product.search([("active", "=", True)])

        for prod in products:
            if self._docai_normalize_text(prod.name or "") == normalized_description:
                _logger.info(
                    "[DocAI] Produit trouvé par nom normalisé pour move %s : %s",
                    self.id,
                    prod.display_name,
                )
                return prod

        product = Product.search([("name", "ilike", description)], limit=1)
        if product:
            _logger.info(
                "[DocAI] Produit trouvé par nom approché pour move %s : %s",
                self.id,
                product.display_name,
            )
            return product

        return False

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
    # RECHERCHE PRODUIT : CONTEXTE FOURNISSEUR PAR PRIX
    # -------------------------------------------------------------------------
    def _docai_find_product_from_supplier_context(self, item_vals):
        """
        Utilisé seulement si description et product_code sont vides.
        On cherche dans les supplierinfo du fournisseur courant avec le prix.
        """
        self.ensure_one()

        if not self.partner_id:
            return False

        SupplierInfo = self.env["product.supplierinfo"].sudo()

        description = (item_vals.get("description") or "").strip()
        product_code = (item_vals.get("product_code") or "").strip()

        if description or product_code:
            return False

        unit_price = self._docai_to_float(item_vals.get("unit_price"), default=0.0)
        amount = self._docai_extract_best_amount(item_vals.get("amount"))

        target_price = unit_price or amount
        if target_price <= 0:
            return False

        supplierinfos = SupplierInfo.search([
            ("partner_id", "=", self.partner_id.id),
            ("product_id", "!=", False),
            ("company_id", "in", [False, self.company_id.id]),
        ], order="id desc")

        if not supplierinfos:
            _logger.info(
                "[DocAI] Aucun supplierinfo pour recherche contexte fournisseur | move=%s | partner=%s",
                self.id,
                self.partner_id.display_name,
            )
            return False

        tolerance = 0.02
        exact_matches = []
        near_matches = []

        for si in supplierinfos:
            si_price = si.price or 0.0
            if si_price <= 0:
                continue

            diff = abs(si_price - target_price)

            if diff <= tolerance:
                exact_matches.append(si.product_id)
            elif diff <= 1.0:
                near_matches.append((diff, si.product_id))

        if exact_matches:
            uniq = []
            seen = set()
            for product in exact_matches:
                if product.id not in seen:
                    uniq.append(product)
                    seen.add(product.id)

            if len(uniq) > 1:
                _logger.warning(
                    "[DocAI] Plusieurs produits trouvés par contexte fournisseur pour move %s : %s",
                    self.id,
                    ", ".join(p.display_name for p in uniq),
                )

            _logger.info(
                "[DocAI] Produit trouvé par contexte fournisseur pour move %s : %s | target_price=%s",
                self.id,
                uniq[0].display_name,
                target_price,
            )
            return uniq[0]

        if near_matches:
            near_matches.sort(key=lambda x: x[0])
            product = near_matches[0][1]
            _logger.info(
                "[DocAI] Produit trouvé par proximité prix fournisseur pour move %s : %s | target_price=%s",
                self.id,
                product.display_name,
                target_price,
            )
            return product

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

        if not product:
            product = self._docai_find_product_from_supplier_context(item_vals)

        return product, item_vals

    # -------------------------------------------------------------------------
    # PRIX FOURNISSEUR
    # -------------------------------------------------------------------------
    def _docai_is_exact_product_name_match(self, product, item_vals):
        self.ensure_one()

        if not product:
            return False

        description = (item_vals.get("description") or "").strip()
        if not description:
            return False

        return (product.name or "").strip() == description

    def _docai_get_last_supplier_price(self, product):
        self.ensure_one()

        if not product or not self.partner_id:
            return 0.0

        SupplierInfo = self.env["product.supplierinfo"].sudo()

        supplierinfo = SupplierInfo.search([
            ("partner_id", "=", self.partner_id.id),
            ("product_tmpl_id", "=", product.product_tmpl_id.id),
            ("product_id", "=", product.id),
            ("company_id", "in", [False, self.company_id.id]),
        ], order="id desc", limit=1)

        if supplierinfo and supplierinfo.price:
            _logger.info(
                "[DocAI] Dernier prix fournisseur trouvé pour move %s | product=%s | partner=%s | price=%s",
                self.id,
                product.display_name,
                self.partner_id.display_name,
                supplierinfo.price,
            )
            return supplierinfo.price

        _logger.info(
            "[DocAI] Aucun dernier prix fournisseur trouvé pour move %s | product=%s | partner=%s",
            self.id,
            product.display_name,
            self.partner_id.display_name if self.partner_id else None,
        )
        return 0.0

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
        if qty <= 0:
            qty = 1.0

        unit_price = self._docai_to_float(item_vals.get("unit_price"), default=0.0)
        amount = self._docai_extract_best_amount(item_vals.get("amount"))

        return bool(
            has_ref_or_name
            and qty > 0
            and (unit_price > 0 or amount > 0)
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
            "description_purchase": "Produit vient d'etre créé",
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

        qty = self._docai_to_float(item_vals.get("quantity"), default=0.0)
        if qty <= 0:
            qty = 1.0

        unit_price = self._docai_to_float(item_vals.get("unit_price"), default=0.0)
        amount = self._docai_extract_best_amount(item_vals.get("amount"))

        if self._docai_is_exact_product_name_match(product, item_vals):
            last_supplier_price = self._docai_get_last_supplier_price(product)
            if last_supplier_price > 0:
                unit_price = last_supplier_price

        if unit_price <= 0 and amount > 0:
            unit_price = amount / qty if qty > 0 else amount

        name = item_vals.get("description") or product.display_name

        return {
            "move_id": self.id,
            "product_id": product.id,
            "name": name,
            "quantity": qty,
            "price_unit": unit_price,
        }

    def _docai_prepare_note_line_vals(self, item_vals):
        self.ensure_one()

        code = (item_vals.get("product_code") or "").strip()
        description = (item_vals.get("description") or "").strip()
        qty = item_vals.get("quantity")
        unit_price = item_vals.get("unit_price")
        amount = item_vals.get("amount")

        parts = []

        if code:
            parts.append(code)

        if description:
            parts.append(description)

        if qty not in (False, None, "", 0):
            parts.append(f"Qté: {qty}")

        if unit_price not in (False, None, "", 0):
            parts.append(f"PU: {unit_price}")

        if amount not in (False, None, "", 0):
            parts.append(f"Montant: {amount}")

        note = " | ".join(parts)

        if not note:
            note = "Ligne DocAI non interprétée"

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

            if not product and self._docai_item_has_minimum_data_for_product_creation(item_vals):
                product = self._docai_create_unvalidated_product(item_vals)

            if product:
                vals = self._docai_prepare_invoice_line_vals(product, item_vals)
                line_model.create(vals)
                _logger.info(
                    "[DocAI] Ligne produit créée pour move %s -> %s | qty=%s | price_unit=%s",
                    self.id,
                    product.display_name,
                    vals.get("quantity"),
                    vals.get("price_unit"),
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
