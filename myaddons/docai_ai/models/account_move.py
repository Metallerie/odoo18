# -*- coding: utf-8 -*-
# account_move.py

import json
import logging
import re
from datetime import datetime

from odoo import api, models, _
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


def _parse_date_any(value):
    """Essaye d'interpréter une date DocAI ou texte libre en YYYY-MM-DD."""
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
        if value.get("text"):
            value = value["text"]
        else:
            value = str(value)

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
    """Nettoie un nombre au format FR/texte libre -> float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    s = s.replace("\u00A0", "").replace(" ", "")
    s = re.sub(r"[^\d,.-]", "", s)

    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")

    try:
        return float(s)
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

    def _docai_get_value(self, ent):
        """Retourne la meilleure valeur disponible : normalizedValue > mentionText."""
        if not ent:
            return None

        norm = ent.get("normalizedValue")
        if norm not in (None, "", {}):
            if isinstance(norm, dict):
                if "floatValue" in norm:
                    return norm["floatValue"]
                if "integerValue" in norm:
                    return norm["integerValue"]
                if "text" in norm:
                    return norm["text"]
                if "dateValue" in norm:
                    return norm
            else:
                return norm

        return ent.get("mentionText")

    def _docai_first_map(self, entities):
        """Map simple type -> première valeur utile."""
        m = {}
        for ent in entities:
            t = ent.get("type") or ent.get("type_")
            val = self._docai_get_value(ent)
            if t and val not in (None, "", {}) and t not in m:
                m[t] = val
        return m

    def _docai_property_map(self, props):
        pmap = {}
        for p in props or []:
            t = _norm_type(p.get("type") or p.get("type_"))
            val = self._docai_get_value(p)
            if t and val not in (None, "", {}) and t not in pmap:
                pmap[t] = val
        return pmap

    def _pick_first(self, data, *keys, default=None):
        for key in keys:
            val = data.get(key)
            if val not in (None, "", {}):
                return val
        return default

    def _docai_normalize_name(self, name):
        if not name:
            return ""
        s = str(name).lower().strip()
        s = s.replace(",", ".")
        s = re.sub(r"[^a-z0-9x.+\- ]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _docai_is_special_charge(self, name, pmap=None):
        txt = " ".join([
            str(name or ""),
            str((pmap or {}).get("description") or ""),
            str((pmap or {}).get("product_code") or ""),
            str((pmap or {}).get("reference") or ""),
            str((pmap or {}).get("unit") or ""),
        ]).lower()
        keywords = (
            "éco-part", "eco-part", "écopart", "ecopart",
            "transport", "port", "emballage", "consigne", "frais",
        )
        return any(k in txt for k in keywords)

    def _is_incomplete_fragment(self, pmap):
        code = str(self._pick_first(pmap, "product_code", "item_code", "code", "reference", default="") or "").strip()
        desc = str(self._pick_first(pmap, "description", "product_name", default="") or "").strip()
        qty = _to_float(pmap.get("quantity"))
        unit_price = _to_float(pmap.get("unit_price"))
        amount = _to_float(pmap.get("amount"))
        unit = str(self._pick_first(pmap, "unit", "uom", default="") or "").strip().upper()

        return bool(code and qty > 0 and not desc and amount == 0.0 and unit_price == 0.0 and unit in ("PI", "P"))

    def _find_tax_from_docai(self, ent_map):
        """Tente de déduire le taux de TVA depuis DocAI."""
        tax_rate = None
        for key in ("vat", "vat/tax_rate"):
            val = ent_map.get(key)
            txt = val.get("text") if isinstance(val, dict) and "text" in val else val
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

        return self.env["account.tax"].search(
            [("amount", "=", tax_rate), ("type_tax_use", "=", "purchase")],
            limit=1,
        ) or False

    # -------------------------------------------------------------------------
    # Catégories / UoM / comptes DocAI
    # -------------------------------------------------------------------------
    def _get_docai_unvalidated_category(self):
        ProductCategory = self.env["product.category"]

        parent = ProductCategory.search([("name", "=", "DocAI"), ("parent_id", "=", False)], limit=1)
        if not parent:
            parent = ProductCategory.create({"name": "DocAI"})

        child = ProductCategory.search([("name", "=", "Non validés"), ("parent_id", "=", parent.id)], limit=1)
        if not child:
            child = ProductCategory.create({"name": "Non validés", "parent_id": parent.id})
        return child

    def _get_docai_default_uom(self, pmap, is_special=False):
        Uom = self.env["uom.uom"]
        unit_name = str(self._pick_first(pmap, "unit", "uom", default="") or "").strip()
        if unit_name and unit_name.upper() not in ("ÉCO-PART", "ECO-PART"):
            uom = Uom.search(["|", ("name", "=", unit_name), ("name", "ilike", unit_name)], limit=1)
            if uom:
                return uom

        fallback_names = ["Unité(s)", "Unité", "Units"] if is_special else []
        for fallback in fallback_names:
            uom = Uom.search([("name", "ilike", fallback)], limit=1)
            if uom:
                return uom
        return False

    def _get_docai_default_expense_account(self, is_special=False):
        ICP = self.env["ir.config_parameter"].sudo()
        key = "docai_ai.default_special_purchase_account_id" if is_special else "docai_ai.default_purchase_account_id"
        account_id = int(ICP.get_param(key, 0) or 0)
        return account_id or False

    # -------------------------------------------------------------------------
    # Recherche produit DocAI
    # -------------------------------------------------------------------------
    def _docai_find_product_by_name(self, name):
        Product = self.env["product.product"]
        if not name:
            return False

        name = str(name).strip()
        product = Product.search([("name", "=ilike", name)], limit=1)
        if product:
            _logger.info("✅ Produit trouvé via nom exact '%s' -> %s", name, product.display_name)
            return product

        product = Product.search([("name", "ilike", name)], limit=1)
        if product:
            _logger.info("✅ Produit trouvé via nom ilike '%s' -> %s", name, product.display_name)
            return product

        normalized = self._docai_normalize_name(name)
        tokens = [tok for tok in normalized.split() if len(tok) >= 2]
        if not tokens:
            return False

        domain = []
        for tok in tokens[:5]:
            domain.append(("name", "ilike", tok))
        product = Product.search(domain, limit=1)
        if product:
            _logger.info("✅ Produit trouvé via tokens '%s' -> %s", tokens[:5], product.display_name)
            return product
        return False

    def _docai_find_product(self, move, pmap, name):
        """Trouve le produit correspondant à une ligne DocAI.
        Priorité : code fournisseur > code interne > nom.
        """
        Product = self.env["product.product"]
        SupplierInfo = self.env["product.supplierinfo"]
        partner = move.partner_id

        raw_code = self._pick_first(pmap, "product_code", "item_code", "code", "reference")
        if raw_code:
            code = str(raw_code).strip()
            if code:
                domain = [("product_code", "=", code)]
                if partner:
                    domain.append(("partner_id", "=", partner.id))
                si = SupplierInfo.search(domain, limit=1)
                if si and si.product_tmpl_id:
                    product = si.product_tmpl_id.product_variant_id
                    _logger.info("✅ Produit trouvé via supplierinfo(partner) code=%s -> %s", code, product.display_name)
                    return product

                product = Product.search([("default_code", "=", code)], limit=1)
                if product:
                    _logger.info("✅ Produit trouvé via default_code exact code=%s -> %s", code, product.display_name)
                    return product

                si = SupplierInfo.search([("product_code", "=", code)], limit=1)
                if si and si.product_tmpl_id:
                    product = si.product_tmpl_id.product_variant_id
                    _logger.info("✅ Produit trouvé via supplierinfo(global) code=%s -> %s", code, product.display_name)
                    return product

        candidate_codes = set()
        for key in ("product_code", "item_code", "code", "reference"):
            raw = pmap.get(key)
            if raw:
                for tok in re.findall(r"\d{3,}", str(raw)):
                    candidate_codes.add(tok)
        if name:
            for tok in re.findall(r"\d{3,}", str(name)):
                candidate_codes.add(tok)

        for code in candidate_codes:
            si_domain = [("product_code", "=", code)]
            if partner:
                si_domain.append(("partner_id", "=", partner.id))
            si = SupplierInfo.search(si_domain, limit=1)
            if si and si.product_tmpl_id:
                product = si.product_tmpl_id.product_variant_id
                _logger.info("✅ Produit trouvé via supplierinfo(partner) candidat=%s -> %s", code, product.display_name)
                return product

        for code in candidate_codes:
            product = Product.search([("default_code", "=", code)], limit=1)
            if product:
                _logger.info("✅ Produit trouvé via default_code exact candidat=%s -> %s", code, product.display_name)
                return product

        for code in candidate_codes:
            product = Product.search([("default_code", "ilike", code)], limit=1)
            if product:
                _logger.info("✅ Produit trouvé via default_code ilike candidat=%s -> %s", code, product.display_name)
                return product

        return self._docai_find_product_by_name(name)

    def _docai_create_product_from_line(self, move, pmap, name):
        ProductTemplate = self.env["product.template"]

        code = str(self._pick_first(pmap, "product_code", "item_code", "code", "reference", default="") or "").strip()
        desc = str(name or self._pick_first(pmap, "description", "product_name", default="") or "").strip()
        if not desc and not code:
            return False

        is_special = self._docai_is_special_charge(desc, pmap)
        categ = self._get_docai_unvalidated_category()
        uom = self._get_docai_default_uom(pmap, is_special=is_special)
        account_id = self._get_docai_default_expense_account(is_special=is_special)

        product_name = f"{code} - {desc}" if code and desc else (desc or code)
        product_name = product_name or _("Produit DocAI")

        existing = False
        if code:
            existing = self.env["product.product"].search([("default_code", "=", code)], limit=1)
        if not existing and desc:
            existing = self._docai_find_product_by_name(desc)
        if existing:
            return existing, False

        vals = {
            "name": product_name,
            "default_code": code or False,
            "categ_id": categ.id,
            "sale_ok": False,
            "purchase_ok": False,
            "detailed_type": "service" if is_special else "consu",
        }
        if uom:
            vals["uom_id"] = uom.id
            vals["uom_po_id"] = uom.id
        if account_id:
            vals["property_account_expense_id"] = account_id

        tmpl = ProductTemplate.create(vals)
        product = tmpl.product_variant_id
        _logger.info("🆕 Produit DocAI créé : %s (code=%s)", product.display_name, code or "-")
        return product, True

    def _docai_find_or_create_product(self, move, pmap, name, unknown_product_id=False):
        product = self._docai_find_product(move, pmap, name)
        if product:
            return product, False

        desc = str(name or "").strip()
        qty = _to_float(pmap.get("quantity"))
        unit_price = _to_float(pmap.get("unit_price"))
        amount = _to_float(pmap.get("amount"))

        if desc and (qty > 0 or unit_price > 0 or amount > 0):
            return self._docai_create_product_from_line(move, pmap, name)

        if unknown_product_id:
            product = self.env["product.product"].browse(unknown_product_id)
            if product.exists():
                _logger.info("⚠️ Aucun produit trouvé pour ligne '%s', utilisation du produit inconnu", name)
                return product, False
        return False, False

    # -------------------------------------------------------------------------
    # Action principale
    # -------------------------------------------------------------------------
    def action_docai_scan_json(self):
        """Analyse le JSON DocAI et génère les lignes de facture."""
        for move in self:
            if not move.docai_json:
                raise UserError(_("Aucun JSON DocAI trouvé sur cette facture."))

            _logger.info("🔎 Analyse JSON pour facture %s (%s)", move.id, move.name or "")

            try:
                data = json.loads(move.docai_json)
            except Exception as e:
                raise UserError(_("JSON invalide : %s") % e)

            entities = self._docai_entities(data)
            if not entities:
                _logger.warning("[DocAI] Facture %s : JSON sans 'entities'", move.id)
                continue

            ent_map = self._docai_first_map(entities)
            vals = {}

            # --- En-tête facture ------------------------------------------------
            if ent_map.get("invoice_id"):
                vals["ref"] = ent_map["invoice_id"]

            if ent_map.get("invoice_date"):
                iso_date = _parse_date_any(ent_map["invoice_date"])
                if iso_date:
                    vals["invoice_date"] = iso_date

            unknown_supplier_id = int(
                self.env["ir.config_parameter"].sudo().get_param("docai_ai.unknown_supplier_id", 0)
            ) or False

            supplier = False
            if ent_map.get("supplier_name"):
                supplier_name = str(ent_map["supplier_name"]).strip()
                supplier = self.env["res.partner"].search([("name", "ilike", supplier_name)], limit=1)
                if not supplier and unknown_supplier_id:
                    supplier = self.env["res.partner"].browse(unknown_supplier_id)

            if supplier:
                if (not move.partner_id) or (unknown_supplier_id and move.partner_id.id == unknown_supplier_id):
                    vals["partner_id"] = supplier.id

            if vals:
                move.write(vals)
                _logger.info("✅ Facture %s mise à jour avec %s", move.id, vals)

            tax = self._find_tax_from_docai(ent_map)

            # -----------------------------------------------------------------
            # Lignes de facture
            # -----------------------------------------------------------------
            line_items = [e for e in entities if (e.get("type") or e.get("type_")) == "line_item"]
            new_lines = []

            purchase_account_id = int(
                self.env["ir.config_parameter"].sudo().get_param("docai_ai.default_purchase_account_id", 0)
            ) or False

            unknown_product_id = int(
                self.env["ir.config_parameter"].sudo().get_param("docai_ai.unknown_product_id", 0)
            ) or False

            for li in line_items:
                props = li.get("properties", []) or []
                pmap = self._docai_property_map(props)

                _logger.debug("[DocAI] mentionText=%s | pmap=%s", li.get("mentionText"), pmap)

                if self._is_incomplete_fragment(pmap):
                    _logger.warning("⚠️ Fragment DocAI ignoré : %s", pmap)
                    continue

                name = self._pick_first(
                    pmap,
                    "description",
                    "product_name",
                    default=(li.get("mentionText") or "Ligne"),
                )

                qty = _to_float(self._pick_first(pmap, "quantity", "qty", default=1.0))
                unit_price = _to_float(self._pick_first(pmap, "unit_price", "price", default=0.0))
                amount = _to_float(self._pick_first(pmap, "amount", "line_amount", default=0.0))

                qty = float_round(qty, precision_digits=3)
                unit_price = float_round(unit_price, precision_digits=3)
                amount = float_round(amount, precision_digits=3)

                if amount <= 0 and qty > 0 and unit_price > 0:
                    amount = float_round(qty * unit_price, precision_digits=3)
                if unit_price <= 0 and qty > 0 and amount > 0:
                    unit_price = float_round(amount / qty, precision_digits=3)
                if qty <= 0 and unit_price > 0 and amount > 0:
                    qty = float_round(amount / unit_price, precision_digits=3)

                if abs(qty) < 1e-6 and abs(unit_price) < 1e-6 and abs(amount) < 1e-6:
                    _logger.info("⚠️ Ligne ignorée (montant nul) : desc=%s pmap=%s", name, pmap)
                    continue

                product, just_created = self._docai_find_or_create_product(move, pmap, name, unknown_product_id)

                uom = False
                uom_name = str(self._pick_first(pmap, "unit", "uom", default="") or "").strip()
                if uom_name and uom_name.upper() not in ("ÉCO-PART", "ECO-PART"):
                    uom = self.env["uom.uom"].search(
                        ["|", ("name", "ilike", uom_name), ("name", "=", uom_name)],
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

                display_name = str(name)
                if product:
                    display_name = product.name
                    if just_created:
                        display_name = f"{product.name} — Ce produit vient d'être créé"

                account_id = False
                if product:
                    account_id = (
                        product.property_account_expense_id.id
                        or product.categ_id.property_account_expense_categ_id.id
                        or False
                    )
                if not account_id and purchase_account_id:
                    account_id = purchase_account_id
                elif not account_id and move.journal_id.default_account_id:
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
