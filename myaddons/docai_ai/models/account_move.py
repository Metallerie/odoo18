# -*- coding: utf-8 -*-
# account_move.py

import json
import logging
import re
from datetime import datetime

from odoo import models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_round

_logger = logging.getLogger(__name__)

# --- Dates helpers -----------------------------------------------------------
MONTHS_FR = {
    "janvier": 1, "janv": 1, "jan": 1,
    "février": 2, "fevrier": 2, "févr": 2, "fevr": 2, "fév": 2, "fev": 2,
    "mars": 3,
    "avril": 4, "avr": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7, "juil": 7,
    "août": 8, "aout": 8,
    "septembre": 9, "sept": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12, "decembre": 12, "déc": 12, "dec": 12,
}

COMMENT_PRODUCT_CREATED = "Ce produit vient d'être créé automatiquement par DocAI."


def _parse_date_any(value):
    """Convertit une date libre en YYYY-MM-DD."""
    if not value:
        return None

    if isinstance(value, dict):
        if value.get("dateValue"):
            try:
                y = int(value["dateValue"]["year"])
                m = int(value["dateValue"]["month"])
                d = int(value["dateValue"]["day"])
                return f"{y:04d}-{m:02d}-{d:02d}"
            except Exception:
                pass
        value = value.get("text") or str(value)

    s = str(value).strip()

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass

    low = s.lower().replace("\u00a0", " ")
    tokens = [t.strip(" .,") for t in low.split() if t.strip()]
    for i in range(len(tokens) - 2):
        d_tok, m_tok, y_tok = tokens[i], tokens[i + 1], tokens[i + 2]
        if d_tok.isdigit() and len(y_tok) == 4 and y_tok.isdigit():
            m_num = MONTHS_FR.get(m_tok)
            if m_num:
                try:
                    d = int(d_tok)
                    y = int(y_tok)
                    if 1 <= d <= 31:
                        return f"{y:04d}-{m_num:02d}-{d:02d}"
                except Exception:
                    pass
    return None


def _to_float(val):
    """Nettoie un nombre FR/texte -> float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    s = s.replace(" ", "").replace("\u00A0", "").replace(",", ".")
    m = re.findall(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return 0.0
    try:
        return float(m[0])
    except Exception:
        return 0.0


class AccountMove(models.Model):
    _inherit = "account.move"

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _looks_numeric_only(self, text):
        text = str(text or "").strip()
        return bool(text) and bool(re.fullmatch(r"[\d\s,.;:()\-€%/]+", text))

    def _clean_text(self, value):
        return str(value or "").strip()

    def _normalize_uom_name(self, unit_value):
        """Le JSON peut contenir 'KG' ou ['Éco', 'PI']."""
        if not unit_value:
            return ""
        if isinstance(unit_value, list):
            cleaned = [str(x).strip() for x in unit_value if str(x).strip()]
            if not cleaned:
                return ""
            return cleaned[-1]
        return str(unit_value).strip()

    def _find_tax_from_json(self, data):
        """Cherche la TVA dans vat[]."""
        vat_lines = data.get("vat") or []
        if not isinstance(vat_lines, list):
            return False

        tax_rate = None
        for vat in vat_lines:
            rate = vat.get("tax_rate")
            if rate:
                txt = str(rate).replace("%", "").replace(",", ".").strip()
                try:
                    tax_rate = float(txt)
                    if 0 <= tax_rate <= 100:
                        break
                except Exception:
                    pass

        if tax_rate is None:
            return False

        tax = self.env["account.tax"].search(
            [("amount", "=", tax_rate), ("type_tax_use", "=", "purchase")],
            limit=1,
        )
        return tax or False

    # -------------------------------------------------------------------------
    # Fournisseur
    # -------------------------------------------------------------------------
    def _docai_find_supplier_by_name(self, supplier_name, unknown_supplier_id=False):
        """Recherche simple par nom."""
        Partner = self.env["res.partner"]
        name = self._clean_text(supplier_name)
        if not name:
            return Partner.browse(unknown_supplier_id) if unknown_supplier_id else False

        partner = Partner.search([("name", "ilike", name)], limit=1)
        if partner:
            _logger.info("✅ Fournisseur trouvé via nom '%s' -> %s", name, partner.display_name)
            return partner

        if unknown_supplier_id:
            return Partner.browse(unknown_supplier_id)

        return False

    # -------------------------------------------------------------------------
    # Catégorie / création produit
    # -------------------------------------------------------------------------
    def _docai_get_or_create_category(self, category_path):
        ProductCategory = self.env["product.category"]
        parent = False

        parts = [p.strip() for p in str(category_path or "").split("/") if p.strip()]
        if not parts:
            parts = ["DocAI", "Non validés"]

        for part in parts:
            domain = [("name", "=", part)]
            if parent:
                domain.append(("parent_id", "=", parent.id))
            else:
                domain.append(("parent_id", "=", False))

            category = ProductCategory.search(domain, limit=1)
            if not category:
                category = ProductCategory.create({
                    "name": part,
                    "parent_id": parent.id if parent else False,
                })
                _logger.info("📁 Catégorie créée : %s", category.complete_name)
            parent = category

        return parent

    def _docai_prepare_product_name(self, line_item):
        description = self._clean_text(line_item.get("description"))
        product_code = self._clean_text(line_item.get("product_code"))

        if description and not self._looks_numeric_only(description):
            return description

        if product_code:
            return f"Produit DocAI {product_code}"

        if description:
            return description

        return "Produit DocAI à valider"

    def _docai_create_product_from_line(self, move, line_item):
        Product = self.env["product.product"]
        SupplierInfo = self.env["product.supplierinfo"]

        product_name = self._docai_prepare_product_name(line_item)
        raw_code = self._clean_text(line_item.get("product_code"))

        category_path = (
            self.env["ir.config_parameter"].sudo().get_param(
                "docai_ai.unvalidated_product_category_path",
                "DocAI / Non validés",
            )
            or "DocAI / Non validés"
        )
        category = self._docai_get_or_create_category(category_path)

        vals = {
            "name": product_name,
            "categ_id": category.id,
            "purchase_ok": True,
            "sale_ok": False,
            "detailed_type": "consu",
            "description_purchase": COMMENT_PRODUCT_CREATED,
        }
        if raw_code:
            vals["default_code"] = raw_code

        product = Product.create(vals)
        _logger.info("🆕 Produit créé automatiquement par DocAI : %s", product.display_name)

        if move.partner_id:
            existing_si = SupplierInfo.search([
                ("partner_id", "=", move.partner_id.id),
                ("product_tmpl_id", "=", product.product_tmpl_id.id),
            ], limit=1)
            if not existing_si:
                SupplierInfo.create({
                    "partner_id": move.partner_id.id,
                    "product_tmpl_id": product.product_tmpl_id.id,
                    "product_code": raw_code or False,
                    "product_name": product_name,
                })
                _logger.info("🔗 Supplierinfo créé pour %s / %s", move.partner_id.display_name, product.display_name)

        try:
            product.product_tmpl_id.message_post(body=COMMENT_PRODUCT_CREATED)
        except Exception:
            _logger.info("ℹ️ Impossible d'ajouter le commentaire chatter sur %s", product.display_name)

        return product

    # -------------------------------------------------------------------------
    # Recherche produit : aller -> inverse
    # -------------------------------------------------------------------------
    def _docai_find_product(self, move, line_item, unknown_product_id=False):
        Product = self.env["product.product"]
        SupplierInfo = self.env["product.supplierinfo"]

        partner = move.partner_id
        product_code = self._clean_text(line_item.get("product_code"))
        description = self._clean_text(line_item.get("description"))

        # -----------------------------------------------------------------
        # 1) RECHERCHE ALLER -> par code
        # -----------------------------------------------------------------
        if product_code:
            if partner:
                si = SupplierInfo.search([
                    ("partner_id", "=", partner.id),
                    ("product_code", "=", product_code),
                ], limit=1)
                if si and si.product_tmpl_id:
                    product = si.product_tmpl_id.product_variant_id
                    _logger.info("✅ Produit trouvé via supplierinfo(partner) code=%s -> %s", product_code, product.display_name)
                    return product

            product = Product.search([("default_code", "=", product_code)], limit=1)
            if product:
                _logger.info("✅ Produit trouvé via default_code exact code=%s -> %s", product_code, product.display_name)
                return product

            si = SupplierInfo.search([("product_code", "=", product_code)], limit=1)
            if si and si.product_tmpl_id:
                product = si.product_tmpl_id.product_variant_id
                _logger.info("✅ Produit trouvé via supplierinfo(global) code=%s -> %s", product_code, product.display_name)
                return product

        # -----------------------------------------------------------------
        # 2) RECHERCHE ALLER -> par description
        # -----------------------------------------------------------------
        if description:
            product = Product.search([("name", "ilike", description)], limit=1)
            if product:
                _logger.info("✅ Produit trouvé via nom '%s' -> %s", description, product.display_name)
                return product

        # -----------------------------------------------------------------
        # 3) RECHERCHE INVERSE
        # -----------------------------------------------------------------
        full_text_parts = [
            description,
            product_code,
            self._clean_text(line_item.get("_mentionText")),
        ]
        full_text = " ".join([x for x in full_text_parts if x]).lower()

        if partner:
            supplier_products = Product.search([
                ("seller_ids.partner_id", "=", partner.id)
            ])

            for prod in supplier_products:
                code = self._clean_text(prod.default_code).lower()
                prod_name = self._clean_text(prod.name).lower()

                if code and code in full_text:
                    _logger.info("✅ Produit trouvé via recherche inverse code='%s' -> %s", code, prod.display_name)
                    return prod

                if prod_name and prod_name in full_text:
                    _logger.info("✅ Produit trouvé via recherche inverse nom='%s' -> %s", prod_name, prod.display_name)
                    return prod

        # -----------------------------------------------------------------
        # 4) Création auto
        # -----------------------------------------------------------------
        try:
            product = self._docai_create_product_from_line(move, line_item)
            if product:
                return product
        except Exception as e:
            _logger.error("❌ Création produit DocAI impossible : %s", e)

        if unknown_product_id:
            product = Product.browse(unknown_product_id)
            _logger.info("⚠️ Aucun produit trouvé, utilisation du produit inconnu")
            return product

        return False

    # -------------------------------------------------------------------------
    # Qualification de ligne
    # -------------------------------------------------------------------------
    def _docai_is_product_line(self, line_item):
        """Règle validée :
        - code seul = produit
        - description seule = produit
        - sinon sans montant = commentaire
        """
        product_code = self._clean_text(line_item.get("product_code"))
        description = self._clean_text(line_item.get("description"))

        if product_code:
            return True
        if description:
            return True
        return False

    def _docai_prepare_comment_label(self, line_item):
        parts = [
            self._clean_text(line_item.get("description")),
            self._clean_text(line_item.get("product_code")),
            self._clean_text(line_item.get("_mentionText")),
        ]
        text = " ".join([p for p in parts if p]).strip()
        return text or "Commentaire DocAI"

    # -------------------------------------------------------------------------
    # Action principale
    # -------------------------------------------------------------------------
    def action_docai_scan_json(self):
        """Analyse le JSON normalisé et génère les lignes de facture."""
        for move in self:
            source_json = move.docai_json_raw or move.docai_json
            if not source_json:
                raise UserError(_("Aucun JSON DocAI trouvé sur cette facture."))

            _logger.info("🔎 Analyse JSON normalisé pour facture %s (%s)", move.id, move.name or "")

            try:
                data = json.loads(source_json)
            except Exception as e:
                raise UserError(_("JSON invalide : %s") % e)

            vals = {}

            # -----------------------------------------------------------------
            # En-tête
            # -----------------------------------------------------------------
            invoice_id = self._clean_text(data.get("invoice_id"))
            if invoice_id:
                vals["ref"] = invoice_id

            invoice_date = _parse_date_any(data.get("invoice_date"))
            if invoice_date:
                vals["invoice_date"] = invoice_date

            unknown_supplier_id = int(
                self.env["ir.config_parameter"].sudo().get_param("docai_ai.unknown_supplier_id", 0)
            ) or False

            supplier = self._docai_find_supplier_by_name(
                data.get("supplier_name"),
                unknown_supplier_id=unknown_supplier_id,
            )

            if supplier:
                if (not move.partner_id) or (unknown_supplier_id and move.partner_id.id == unknown_supplier_id):
                    vals["partner_id"] = supplier.id

            if vals:
                move.write(vals)
                _logger.info("✅ Facture %s mise à jour avec %s", move.id, vals)

            tax = self._find_tax_from_json(data)

            # -----------------------------------------------------------------
            # Lignes
            # -----------------------------------------------------------------
            line_items = data.get("line_items") or []
            if not isinstance(line_items, list):
                line_items = []

            new_lines = []

            purchase_account_id = int(
                self.env["ir.config_parameter"].sudo().get_param("docai_ai.default_purchase_account_id", 0)
            ) or False

            unknown_product_id = int(
                self.env["ir.config_parameter"].sudo().get_param("docai_ai.unknown_product_id", 0)
            ) or False

            for line_item in line_items:
                if not isinstance(line_item, dict):
                    continue

                amount = float_round(_to_float(line_item.get("amount")), precision_digits=3)
                qty = float_round(_to_float(line_item.get("quantity")), precision_digits=3)
                unit_price = float_round(_to_float(line_item.get("unit_price")), precision_digits=3)

                is_product_line = self._docai_is_product_line(line_item)

                # -----------------------------------------------------------------
                # LIGNE PRODUIT
                # -----------------------------------------------------------------
                if is_product_line:
                    # recalculs simples
                    if amount <= 0 and qty > 0 and unit_price > 0:
                        amount = float_round(qty * unit_price, precision_digits=3)

                    if unit_price <= 0 and qty > 0 and amount > 0:
                        unit_price = float_round(amount / qty, precision_digits=3)

                    if qty <= 0:
                        qty = 1.0

                    product = self._docai_find_product(move, line_item, unknown_product_id=unknown_product_id)

                    unit_name = self._normalize_uom_name(line_item.get("unit"))
                    uom = False
                    if unit_name:
                        uom = self.env["uom.uom"].search([
                            "|",
                            ("name", "ilike", unit_name),
                            ("name", "=", unit_name),
                        ], limit=1)

                    product_uom_id = False
                    if product and uom:
                        if product.uom_id.category_id == uom.category_id:
                            product_uom_id = uom.id
                        else:
                            _logger.info(
                                "⚠️ UoM incompatible (%s) ignorée pour %s, on garde %s",
                                uom.name, product.display_name, product.uom_id.name
                            )
                            product_uom_id = product.uom_id.id
                    elif product:
                        product_uom_id = product.uom_id.id

                    display_name = product.name if product else self._docai_prepare_product_name(line_item)

                    account_id = False
                    if purchase_account_id:
                        account_id = purchase_account_id
                    elif move.journal_id.default_account_id:
                        account_id = move.journal_id.default_account_id.id

                    line_vals = {
                        "name": display_name,
                        "quantity": qty,
                        "price_unit": unit_price,
                        "product_id": product.id if product else False,
                        "product_uom_id": product_uom_id,
                        "account_id": account_id,
                    }
                    if tax:
                        line_vals["tax_ids"] = [(6, 0, [tax.id])]

                    new_lines.append((0, 0, line_vals))
                    continue

                # -----------------------------------------------------------------
                # LIGNE COMMENTAIRE
                # -----------------------------------------------------------------
                comment_label = self._docai_prepare_comment_label(line_item)
                if amount <= 0:
                    new_lines.append((0, 0, {
                        "display_type": "line_note",
                        "name": comment_label,
                    }))
                    _logger.info("📝 Ligne commentaire créée : %s", comment_label)
                    continue

                # sécurité
                _logger.info("⚠️ Ligne ignorée : %s", line_item)

            # -----------------------------------------------------------------
            # Écriture sur la facture
            # -----------------------------------------------------------------
            if new_lines:
                move.write({"invoice_line_ids": [(5, 0, 0)] + new_lines})
                move._compute_amount()
                _logger.info("✅ %s lignes importées pour facture %s", len(new_lines), move.id)
            else:
                _logger.warning("⚠️ Aucune ligne détectée/importée pour facture %s", move.id)

    # -------------------------------------------------------------------------
    # CRON
    # -------------------------------------------------------------------------
    @api.model
    def cron_docai_parse_json(self):
        """CRON : applique le parsing JSON sur les factures fournisseurs en brouillon."""
        moves = self.env["account.move"].search(
            [
                ("move_type", "=", "in_invoice"),
                ("state", "=", "draft"),
                ("docai_json", "!=", False),
                ("invoice_line_ids", "=", False),
                ("amount_total", "=", 0),
            ],
            limit=10,
        )

        _logger.info("[DocAI JSON CRON] %s factures à interpréter", len(moves))

        for move in moves:
            try:
                move.action_docai_scan_json()
                _logger.info("✅ Facture %s (%s) mise à jour via JSON", move.id, move.name or "")
            except Exception as e:
                _logger.error("❌ Erreur JSON Facture %s: %s", move.id, e)
                continue
