# -*- coding: utf-8 -*-
# account_move.py

import json
import logging
import re
from datetime import datetime

from odoo import models, fields, api, _
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
    """Essaye d'interpréter une date DocAI ou texte libre en YYYY-MM-DD."""
    if not value:
        return None

    # DocAI dateValue
    if isinstance(value, dict):
        if value.get("dateValue"):
            try:
                y = int(value["dateValue"]["year"])
                m = int(value["dateValue"]["month"])
                d = int(value["dateValue"]["day"])
                return f"{y:04d}-{m:02d}-{d:02d}"
            except Exception:
                pass
        if value.get("text"):
            value = value["text"]
        else:
            value = str(value)

    s = str(value).strip()

    # Formats classiques
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass

    # Formats "14 novembre 2025"
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
    """Nettoie un nombre au format FR/texte libre -> float."""
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


def _norm_type(t):
    if not t:
        return ""
    return str(t).split("/")[-1]


class AccountMove(models.Model):
    _inherit = "account.move"

    # -------------------------------------------------------------------------
    # Helpers DocAI
    # -------------------------------------------------------------------------
    def _docai_entities(self, data):
        ents = data.get("entities")
        return ents if isinstance(ents, list) else []

    def _docai_first_map(self, entities):
        """Map simple type -> première valeur normalisée."""
        m = {}
        for ent in entities:
            t = ent.get("type") or ent.get("type_")
            txt = ent.get("mentionText")
            if t and txt and t not in m:
                m[t] = ent.get("normalizedValue", txt)
        return m

    def _looks_numeric_only(self, text):
        text = str(text or "").strip()
        return bool(text) and bool(re.fullmatch(r"[\d\s,.;:()\-€%/]+", text))

    def _extract_leboncoin_label(self, full_text, unit_price, amount):
        """Fallback simple pour les factures Leboncoin.
        Cherche le motif : description / prix HT / TVA / prix TTC.
        """
        if not full_text:
            return False

        lines = [l.strip() for l in str(full_text).splitlines() if l.strip()]
        ht = f"{float(unit_price):.2f}€".replace(".", ",") if unit_price else ""
        ttc = f"{float(amount):.2f}€".replace(".", ",") if amount else ""

        if not ht or not ttc:
            return False

        for i in range(len(lines) - 3):
            if lines[i + 1] == ht and "%" in lines[i + 2] and lines[i + 3] == ttc:
                candidate = lines[i]
                if candidate and not self._looks_numeric_only(candidate):
                    return candidate
        return False

    def _find_tax_from_docai(self, ent_map):
        """Tente de déduire le taux de TVA depuis les entités DocAI."""
        tax_rate = None
        for key in ("vat", "vat/tax_rate", "total_tax_amount"):
            val = ent_map.get(key)
            if isinstance(val, dict) and "text" in val:
                txt = val["text"]
            else:
                txt = val
            if txt:
                txt = str(txt).replace("%", "").replace(",", ".").strip()
                try:
                    tax_rate = float(txt)
                    if 1 <= tax_rate <= 100:
                        break
                except Exception:
                    continue

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
    def _docai_find_supplier_by_name(self, ent_map, unknown_supplier_id=False):
        """Recherche simple du fournisseur par nom dans plusieurs champs DocAI.
        On commence volontairement par le nom uniquement.
        """
        Partner = self.env["res.partner"]

        candidate_names = [
            ent_map.get("supplier_name"),
            ent_map.get("receiver_name"),
            ent_map.get("ship_to_name"),
        ]

        for raw_name in candidate_names:
            name = str(raw_name or "").strip()
            if not name:
                continue

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
        """Crée au besoin une hiérarchie de catégories de type 'DocAI / Non validés'."""
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

    def _docai_prepare_product_name(self, name, pmap):
        name = str(name or "").strip()
        if name and not self._looks_numeric_only(name):
            return name

        for key in ("product_name", "item_name", "description", "reference"):
            value = str(pmap.get(key) or "").strip()
            if value and not self._looks_numeric_only(value):
                return value

        raw_code = (
            pmap.get("product_code")
            or pmap.get("item_code")
            or pmap.get("code")
            or pmap.get("reference")
        )
        raw_code = str(raw_code or "").strip()
        if raw_code:
            return f"Produit DocAI {raw_code}"

        return "Produit DocAI à valider"

    def _docai_create_product_from_line(self, move, pmap, name):
        """Crée un produit minimal dans DocAI / Non validés.
        On reste volontairement simple et réversible.
        """
        Product = self.env["product.product"]
        SupplierInfo = self.env["product.supplierinfo"]

        product_name = self._docai_prepare_product_name(name, pmap)
        raw_code = (
            pmap.get("product_code")
            or pmap.get("item_code")
            or pmap.get("code")
            or pmap.get("reference")
        )
        raw_code = str(raw_code or "").strip()

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
        _logger.info(
            "🆕 Produit créé automatiquement par DocAI : %s (id=%s)",
            product.display_name,
            product.id,
        )

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
                _logger.info(
                    "🔗 Supplierinfo créé pour %s / %s",
                    move.partner_id.display_name,
                    product.display_name,
                )

        try:
            product.product_tmpl_id.message_post(body=COMMENT_PRODUCT_CREATED)
        except Exception:
            _logger.info("ℹ️ Impossible d'ajouter le commentaire chatter sur %s", product.display_name)

        return product

    # -------------------------------------------------------------------------
    # Recherche produit DocAI
    # -------------------------------------------------------------------------
    def _docai_find_product(self, move, pmap, name, unknown_product_id):
        """Trouve le produit correspondant à une ligne DocAI.

        Ordre :
        1. JSON -> Odoo par code (supplierinfo du fournisseur, puis default_code)
        2. Heuristiques code
        3. Recherche par nom chez le fournisseur quand il est connu
        4. Recherche globale prudente par nom
        5. Création automatique dans 'DocAI / Non validés'
        6. Produit inconnu seulement si la création échoue
        """
        Product = self.env["product.product"]
        SupplierInfo = self.env["product.supplierinfo"]

        partner = move.partner_id
        product = None

        # 1) PRIORITÉ : product_code direct
        raw_code = (
            pmap.get("product_code")
            or pmap.get("item_code")
            or pmap.get("code")
            or pmap.get("reference")
        )
        if raw_code:
            code = str(raw_code).strip()
            if code:
                # supplierinfo pour CE fournisseur
                if partner:
                    si = SupplierInfo.search([
                        ("partner_id", "=", partner.id),
                        ("product_code", "=", code),
                    ], limit=1)
                    if si and si.product_tmpl_id:
                        product = si.product_tmpl_id.product_variant_id
                        _logger.info(
                            "✅ Produit trouvé via supplierinfo(partner) code=%s -> %s",
                            code, product.display_name,
                        )
                        return product

                # code interne exact
                product = Product.search([("default_code", "=", code)], limit=1)
                if product:
                    _logger.info(
                        "✅ Produit trouvé via default_code exact code=%s -> %s",
                        code, product.display_name,
                    )
                    return product

                # supplierinfo global
                si = SupplierInfo.search([("product_code", "=", code)], limit=1)
                if si and si.product_tmpl_id:
                    product = si.product_tmpl_id.product_variant_id
                    _logger.info(
                        "✅ Produit trouvé via supplierinfo(global) code=%s -> %s",
                        code, product.display_name,
                    )
                    return product

        # 2) Heuristique : on cherche des codes numériques dans les champs texte
        candidate_codes = set()
        for key in ("product_code", "item_code", "code", "reference"):
            if pmap.get(key):
                raw = str(pmap[key]).strip()
                if raw:
                    for tok in re.findall(r"\d{3,}", raw):
                        candidate_codes.add(tok)

        if name and not self._looks_numeric_only(name):
            for tok in re.findall(r"\d{3,}", str(name)):
                candidate_codes.add(tok)

        candidate_codes = list(candidate_codes)
        if candidate_codes:
            _logger.info("[DocAI] Codes candidats pour '%s' : %s", name, candidate_codes)

        # 2.a) supplierinfo pour CE fournisseur
        if partner:
            for code in candidate_codes:
                si = SupplierInfo.search([
                    ("partner_id", "=", partner.id),
                    ("product_code", "=", code),
                ], limit=1)
                if si and si.product_tmpl_id:
                    product = si.product_tmpl_id.product_variant_id
                    _logger.info(
                        "✅ Produit trouvé via supplierinfo(partner) candidat=%s -> %s",
                        code, product.display_name,
                    )
                    return product

        # 2.b) default_code exact / ilike
        for code in candidate_codes:
            product = Product.search([("default_code", "=", code)], limit=1)
            if product:
                _logger.info(
                    "✅ Produit trouvé via default_code exact candidat=%s -> %s",
                    code, product.display_name,
                )
                return product

        for code in candidate_codes:
            if len(code) >= 5:
                product = Product.search([("default_code", "ilike", code)], limit=1)
                if product:
                    _logger.info(
                        "✅ Produit trouvé via default_code ilike candidat=%s -> %s",
                        code, product.display_name,
                    )
                    return product

        # 3) Recherche par nom restreinte au fournisseur via supplierinfo
        if partner and name and not self._looks_numeric_only(name):
            sis = SupplierInfo.search([
                ("partner_id", "=", partner.id),
                "|",
                ("product_name", "ilike", name),
                ("product_tmpl_id.name", "ilike", name),
            ], limit=5)
            if sis:
                product = sis[0].product_tmpl_id.product_variant_id
                if product:
                    _logger.info(
                        "✅ Produit trouvé via supplierinfo(partner) nom='%s' -> %s",
                        name, product.display_name,
                    )
                    return product

        # 4) Recherche globale prudente par nom
        if name and not self._looks_numeric_only(name):
            product = Product.search([("name", "ilike", name)], limit=1)
            if product:
                _logger.info(
                    "✅ Produit trouvé via nom ilike '%s' -> %s",
                    name, product.display_name,
                )
                return product

        # 5) Création automatique d'un produit à valider
        try:
            product = self._docai_create_product_from_line(move, pmap, name)
            if product:
                return product
        except Exception as e:
            _logger.error("❌ Création produit DocAI impossible pour '%s' : %s", name, e)

        # 6) Dernier recours : produit inconnu
        if unknown_product_id:
            product = Product.browse(unknown_product_id)
            _logger.info(
                "⚠️ Aucun produit trouvé pour ligne '%s', utilisation du produit inconnu",
                name,
            )
            return product

        return False

    # -------------------------------------------------------------------------
    # Action principale
    # -------------------------------------------------------------------------
    def action_docai_scan_json(self):
        """Analyse le JSON DocAI et génère les lignes de facture."""
        for move in self:
            source_json = move.docai_json_raw or move.docai_json
            if not source_json:
                raise UserError(_("Aucun JSON DocAI trouvé sur cette facture."))

            _logger.info("🔎 Analyse JSON pour facture %s (%s)", move.id, move.name or "")

            try:
                data = json.loads(source_json)
            except Exception as e:
                raise UserError(_("JSON invalide : %s") % e)

            entities = self._docai_entities(data)
            if not entities:
                _logger.warning("[DocAI] Facture %s : JSON sans 'entities'", move.id)
                continue

            ent_map = self._docai_first_map(entities)
            vals = {}
            full_text = data.get("text") or ""

            # --- En-tête facture ------------------------------------------------
            if ent_map.get("invoice_id"):
                vals["ref"] = ent_map["invoice_id"]

            if ent_map.get("invoice_date"):
                iso_date = _parse_date_any(ent_map["invoice_date"])
                if iso_date:
                    vals["invoice_date"] = iso_date

            # Fournisseur
            unknown_supplier_id = int(
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("docai_ai.unknown_supplier_id", 0)
            ) or False

            supplier = self._docai_find_supplier_by_name(ent_map, unknown_supplier_id)

            if supplier:
                if (not move.partner_id) or (
                    unknown_supplier_id and move.partner_id.id == unknown_supplier_id
                ):
                    vals["partner_id"] = supplier.id

            if vals:
                move.write(vals)
                _logger.info("✅ Facture %s mise à jour avec %s", move.id, vals)

            # TVA
            tax = self._find_tax_from_docai(ent_map)

            # -----------------------------------------------------------------
            # Lignes de facture
            # -----------------------------------------------------------------
            line_items = [
                e for e in entities
                if (e.get("type") or e.get("type_")) == "line_item"
            ]
            new_lines = []

            purchase_account_id = int(
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("docai_ai.default_purchase_account_id", 0)
            ) or False

            unknown_product_id = int(
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("docai_ai.unknown_product_id", 0)
            ) or False

            for li in line_items:
                props = li.get("properties", []) or []
                pmap = {}
                for p in props:
                    t = _norm_type(p.get("type") or p.get("type_"))
                    txt = p.get("mentionText")
                    if t and txt and t not in pmap:
                        pmap[t] = txt

                name = pmap.get("description") or ""

                qty = _to_float(pmap.get("quantity") or 1.0)
                unit_price = _to_float(pmap.get("unit_price") or 0.0)
                amount = _to_float(pmap.get("amount") or 0.0)

                # Arrondis propres
                qty = float_round(qty, precision_digits=3)
                unit_price = float_round(unit_price, precision_digits=3)
                amount = float_round(amount, precision_digits=3)

                if not name or self._looks_numeric_only(name):
                    fallback_name = self._extract_leboncoin_label(full_text, unit_price, amount)
                    if fallback_name:
                        name = fallback_name

                if not name:
                    name = "Ligne"

                _logger.debug(
                    "[DocAI] Ligne brute : desc=%s qty=%s unit_price=%s amount=%s pmap=%s",
                    name, qty, unit_price, amount, pmap,
                )

                # Recalcule si un des trois manque
                if amount <= 0 and qty > 0 and unit_price > 0:
                    amount = float_round(qty * unit_price, precision_digits=3)
                if unit_price <= 0 and qty > 0 and amount > 0:
                    unit_price = float_round(amount / qty, precision_digits=3)
                if qty <= 0 and unit_price > 0 and amount > 0:
                    qty = float_round(amount / unit_price, precision_digits=3)

                # Ligne fantôme → on zappe
                if abs(qty) < 1e-6 and abs(unit_price) < 1e-6 and abs(amount) < 1e-6:
                    _logger.info(
                        "⚠️ Ligne ignorée (montant nul) : desc=%s pmap=%s", name, pmap
                    )
                    continue

                # -----------------------------------------------------------------
                # Produit
                # -----------------------------------------------------------------
                product = self._docai_find_product(move, pmap, name, unknown_product_id)

                # -----------------------------------------------------------------
                # UoM sécurisée
                # -----------------------------------------------------------------
                uom = None
                if pmap.get("unit") or pmap.get("uom"):
                    uom_name = (pmap.get("unit") or pmap.get("uom") or "").strip()
                    if uom_name:
                        uom = self.env["uom.uom"].search(
                            [
                                "|",
                                ("name", "ilike", uom_name),
                                ("name", "=", uom_name),
                            ],
                            limit=1,
                        )

                product_uom_id = False
                if product and uom:
                    if product.uom_id.category_id == uom.category_id:
                        product_uom_id = uom.id
                    else:
                        _logger.info(
                            "⚠️ UoM incompatible (%s) ignorée pour le produit %s — on garde %s",
                            uom.name, product.name, product.uom_id.name,
                        )
                        product_uom_id = product.uom_id.id
                elif product:
                    product_uom_id = product.uom_id.id
                else:
                    product_uom_id = False

                if product and unknown_product_id and product.id == unknown_product_id:
                    product_uom_id = product.uom_id.id

                display_name = product.name if product else name

                account_id = False
                if purchase_account_id:
                    account_id = purchase_account_id
                elif move.journal_id.default_account_id:
                    account_id = move.journal_id.default_account_id.id

                line_vals = {
                    "name": display_name,
                    "quantity": qty if qty > 0 else 1.0,
                    "price_unit": unit_price,
                    "product_id": product.id if product else False,
                    "product_uom_id": product_uom_id,
                    "account_id": account_id,
                }
                if tax:
                    line_vals["tax_ids"] = [(6, 0, [tax.id])]

                new_lines.append((0, 0, line_vals))

            # -----------------------------------------------------------------
            # Écriture sur la facture
            # -----------------------------------------------------------------
            if new_lines:
                move.write({"invoice_line_ids": [(5, 0, 0)] + new_lines})
                move._compute_amount()  # Odoo 18
                _logger.info(
                    "✅ %s lignes importées pour facture %s", len(new_lines), move.id
                )
            else:
                _logger.warning(
                    "⚠️ Aucune ligne détectée/importée pour facture %s", move.id
                )

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
                _logger.info(
                    "✅ Facture %s (%s) mise à jour via JSON",
                    move.id,
                    move.name or "",
                )
            except Exception as e:
                _logger.error("❌ Erreur JSON Facture %s: %s", move.id, e)
                continue
