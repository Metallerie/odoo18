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

# -------------------------------------------------------------------------
# Dates helpers
# -------------------------------------------------------------------------
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

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------
    def _looks_numeric_only(self, text):
        text = str(text or "").strip()
        return bool(text) and bool(re.fullmatch(r"[\d\s,.;:()\-€%/]+", text))

    def _clean_text(self, value):
        return str(value or "").strip()

    def _normalize_uom_name(self, unit_value):
        if not unit_value:
            return ""
        if isinstance(unit_value, list):
            cleaned = [str(x).strip() for x in unit_value if str(x).strip()]
            if not cleaned:
                return ""
            return cleaned[-1]
        return str(unit_value).strip()

    def _find_tax_from_json(self, data):
        vat_lines = data.get("vat") or []
        if not isinstance(vat_lines, list):
            _logger.info("[DocAI] TVA : vat n'est pas une liste")
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
            _logger.info("[DocAI] TVA : aucun taux détecté")
            return False

        tax = self.env["account.tax"].search(
            [("amount", "=", tax_rate), ("type_tax_use", "=", "purchase")],
            limit=1,
        )
        _logger.info("[DocAI] TVA recherchée=%s -> tax=%s", tax_rate, tax.display_name if tax else "NON TROUVÉE")
        return tax or False

    # ---------------------------------------------------------------------
    # Fournisseur
    # ---------------------------------------------------------------------
    def _docai_find_supplier_by_name(self, supplier_name, unknown_supplier_id=False):
        Partner = self.env["res.partner"]
        name = self._clean_text(supplier_name)
        _logger.info("[DocAI] Recherche fournisseur par nom='%s'", name)

        if not name:
            if unknown_supplier_id:
                _logger.info("[DocAI] Fournisseur vide, fallback fournisseur inconnu id=%s", unknown_supplier_id)
                return Partner.browse(unknown_supplier_id)
            return False

        partner = Partner.search([("name", "ilike", name)], limit=1)
        if partner:
            _logger.info("[DocAI] ✅ Fournisseur trouvé : %s (id=%s)", partner.display_name, partner.id)
            return partner

        _logger.info("[DocAI] ❌ Fournisseur introuvable par nom='%s'", name)

        if unknown_supplier_id:
            fallback = Partner.browse(unknown_supplier_id)
            _logger.info("[DocAI] Fallback fournisseur inconnu -> %s", fallback.display_name if fallback else "AUCUN")
            return fallback

        return False

    # ---------------------------------------------------------------------
    # Catégorie / création produit
    # ---------------------------------------------------------------------
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
                _logger.info("[DocAI] 📁 Catégorie créée : %s", category.complete_name)
            else:
                _logger.info("[DocAI] 📁 Catégorie trouvée : %s", category.complete_name)
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

        _logger.info("[DocAI] Création produit : name='%s' code='%s'", product_name, raw_code)

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

        _logger.info("[DocAI] Product.create vals=%s", vals)
        product = Product.create(vals)
        _logger.info("[DocAI] 🆕 Produit créé : %s (id=%s)", product.display_name, product.id)

        if move.partner_id:
            existing_si = SupplierInfo.search([
                ("partner_id", "=", move.partner_id.id),
                ("product_tmpl_id", "=", product.product_tmpl_id.id),
            ], limit=1)
            if not existing_si:
                si_vals = {
                    "partner_id": move.partner_id.id,
                    "product_tmpl_id": product.product_tmpl_id.id,
                    "product_code": raw_code or False,
                    "product_name": product_name,
                }
                _logger.info("[DocAI] SupplierInfo.create vals=%s", si_vals)
                SupplierInfo.create(si_vals)
                _logger.info("[DocAI] 🔗 Supplierinfo créé pour %s / %s", move.partner_id.display_name, product.display_name)

        try:
            product.product_tmpl_id.message_post(body=COMMENT_PRODUCT_CREATED)
        except Exception as e:
            _logger.info("[DocAI] Impossible d'ajouter le commentaire chatter : %s", e)

        return product

    # ---------------------------------------------------------------------
    # Recherche produit aller -> inverse
    # ---------------------------------------------------------------------
    def _docai_find_product(self, move, line_item, unknown_product_id=False):
        Product = self.env["product.product"]
        SupplierInfo = self.env["product.supplierinfo"]

        partner = move.partner_id
        product_code = self._clean_text(line_item.get("product_code"))
        description = self._clean_text(line_item.get("description"))
        mention_text = self._clean_text(line_item.get("_mentionText"))

        _logger.info(
            "[DocAI] Recherche produit start | partner=%s | code='%s' | description='%s' | mention='%s'",
            partner.display_name if partner else "AUCUN",
            product_code,
            description,
            mention_text,
        )

        # 1) ALLER PAR CODE
        if product_code:
            _logger.info("[DocAI] Recherche ALLER par code='%s'", product_code)

            if partner:
                si = SupplierInfo.search([
                    ("partner_id", "=", partner.id),
                    ("product_code", "=", product_code),
                ], limit=1)
                if si and si.product_tmpl_id:
                    product = si.product_tmpl_id.product_variant_id
                    _logger.info("[DocAI] ✅ Trouvé via supplierinfo(partner) -> %s", product.display_name)
                    return product

            product = Product.search([("default_code", "=", product_code)], limit=1)
            if product:
                _logger.info("[DocAI] ✅ Trouvé via default_code exact -> %s", product.display_name)
                return product

            si = SupplierInfo.search([("product_code", "=", product_code)], limit=1)
            if si and si.product_tmpl_id:
                product = si.product_tmpl_id.product_variant_id
                _logger.info("[DocAI] ✅ Trouvé via supplierinfo(global) -> %s", product.display_name)
                return product

            _logger.info("[DocAI] ❌ Rien trouvé par code='%s'", product_code)

        # 2) ALLER PAR DESCRIPTION
        if description:
            _logger.info("[DocAI] Recherche ALLER par description='%s'", description)
            product = Product.search([("name", "ilike", description)], limit=1)
            if product:
                _logger.info("[DocAI] ✅ Trouvé via nom -> %s", product.display_name)
                return product
            _logger.info("[DocAI] ❌ Rien trouvé par description='%s'", description)

        # 3) INVERSE
        full_text = " ".join([x for x in [description, product_code, mention_text] if x]).lower()
        _logger.info("[DocAI] Recherche INVERSE dans full_text='%s'", full_text)

        if partner:
            supplier_products = Product.search([("seller_ids.partner_id", "=", partner.id)])
            _logger.info("[DocAI] Produits fournisseur trouvés pour inverse : %s", len(supplier_products))

            for prod in supplier_products:
                code = self._clean_text(prod.default_code).lower()
                prod_name = self._clean_text(prod.name).lower()

                if code and code in full_text:
                    _logger.info("[DocAI] ✅ Trouvé en INVERSE par code produit='%s' -> %s", code, prod.display_name)
                    return prod

                if prod_name and prod_name in full_text:
                    _logger.info("[DocAI] ✅ Trouvé en INVERSE par nom produit='%s' -> %s", prod_name, prod.display_name)
                    return prod

        _logger.info("[DocAI] ❌ Recherche inverse sans résultat")

        # 4) CREATION AUTO
        try:
            product = self._docai_create_product_from_line(move, line_item)
            if product:
                _logger.info("[DocAI] ✅ Produit créé automatiquement -> %s", product.display_name)
                return product
        except Exception as e:
            _logger.exception("[DocAI] ❌ Erreur création produit")
            _logger.error("[DocAI] Détail erreur création produit : %s", e)

        # 5) FALLBACK
        if unknown_product_id:
            product = Product.browse(unknown_product_id)
            _logger.info("[DocAI] ⚠️ Fallback produit inconnu -> %s", product.display_name if product else "AUCUN")
            return product

        _logger.info("[DocAI] ❌ Aucun produit trouvé au final")
        return False

    # ---------------------------------------------------------------------
    # Qualification ligne
    # ---------------------------------------------------------------------
    def _docai_is_product_line(self, line_item):
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

    def _docai_get_expense_account(self, move, product):
        purchase_account_id = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "docai_ai.default_purchase_account_id", 0
            )
        ) or False

        if purchase_account_id:
            _logger.info("[DocAI] Compte charge depuis paramètre=%s", purchase_account_id)
            return purchase_account_id

        if product:
            if product.property_account_expense_id:
                _logger.info("[DocAI] Compte charge depuis produit=%s", product.property_account_expense_id.id)
                return product.property_account_expense_id.id

            categ_acc = product.categ_id.property_account_expense_categ_id
            if categ_acc:
                _logger.info("[DocAI] Compte charge depuis catégorie=%s", categ_acc.id)
                return categ_acc.id

        if move.journal_id.default_account_id:
            _logger.info("[DocAI] Compte charge depuis journal=%s", move.journal_id.default_account_id.id)
            return move.journal_id.default_account_id.id

        _logger.info("[DocAI] ❌ Aucun compte de charge trouvé")
        return False

    # ---------------------------------------------------------------------
    # Action principale
    # ---------------------------------------------------------------------
    def action_docai_scan_json(self):
        _logger.info("============================================================")
        _logger.info("[DocAI] BOUTON action_docai_scan_json APPELÉ")
        _logger.info("============================================================")

        for move in self:
            try:
                _logger.info("[DocAI] ---- Début traitement facture id=%s name=%s ----", move.id, move.name or "")
                _logger.info("[DocAI] move_type=%s state=%s partner=%s", move.move_type, move.state, move.partner_id.display_name or "")

                source_json = move.docai_json_raw or move.docai_json
                if not source_json:
                    _logger.error("[DocAI] Aucun JSON sur facture id=%s", move.id)
                    raise UserError(_("Aucun JSON DocAI trouvé sur cette facture."))

                _logger.info("[DocAI] JSON trouvé, taille=%s caractères", len(source_json))

                try:
                    data = json.loads(source_json)
                except Exception as e:
                    _logger.exception("[DocAI] JSON invalide")
                    raise UserError(_("JSON invalide : %s") % e)

                _logger.info("[DocAI] JSON chargé avec succès")
                _logger.info("[DocAI] Clés JSON=%s", list(data.keys()))

                vals = {}

                # ---------------------------------------------------------
                # En-tête
                # ---------------------------------------------------------
                invoice_id = self._clean_text(data.get("invoice_id"))
                invoice_date = _parse_date_any(data.get("invoice_date"))
                supplier_name = self._clean_text(data.get("supplier_name"))

                _logger.info(
                    "[DocAI] Entête : invoice_id='%s' invoice_date='%s' supplier_name='%s'",
                    invoice_id, invoice_date, supplier_name
                )

                if invoice_id:
                    vals["ref"] = invoice_id

                if invoice_date:
                    vals["invoice_date"] = invoice_date

                unknown_supplier_id = int(
                    self.env["ir.config_parameter"].sudo().get_param(
                        "docai_ai.unknown_supplier_id", 0
                    )
                ) or False

                supplier = self._docai_find_supplier_by_name(
                    supplier_name,
                    unknown_supplier_id=unknown_supplier_id,
                )

                if supplier:
                    if (not move.partner_id) or (unknown_supplier_id and move.partner_id.id == unknown_supplier_id):
                        vals["partner_id"] = supplier.id
                        _logger.info("[DocAI] partner_id sera mis à jour -> %s", supplier.id)
                    else:
                        _logger.info("[DocAI] partner existant conservé -> %s", move.partner_id.display_name)
                else:
                    _logger.info("[DocAI] Aucun fournisseur trouvé à écrire")

                if vals:
                    _logger.info("[DocAI] move.write entête vals=%s", vals)
                    move.write(vals)
                    _logger.info("[DocAI] ✅ Entête écrite")
                else:
                    _logger.info("[DocAI] Aucun champ entête à écrire")

                # Recharge move si partner_id a changé
                move.flush_recordset()
                move.invalidate_recordset()

                tax = self._find_tax_from_json(data)

                # ---------------------------------------------------------
                # Lignes
                # ---------------------------------------------------------
                line_items = data.get("line_items") or []
                if not isinstance(line_items, list):
                    line_items = []

                _logger.info("[DocAI] Nombre de line_items=%s", len(line_items))

                new_lines = []

                unknown_product_id = int(
                    self.env["ir.config_parameter"].sudo().get_param(
                        "docai_ai.unknown_product_id", 0
                    )
                ) or False

                for idx, line_item in enumerate(line_items, start=1):
                    _logger.info("------------------------------------------------------------")
                    _logger.info("[DocAI] Ligne #%s brute=%s", idx, line_item)

                    if not isinstance(line_item, dict):
                        _logger.info("[DocAI] Ligne #%s ignorée : pas un dict", idx)
                        continue

                    amount = float_round(_to_float(line_item.get("amount")), precision_digits=3)
                    qty = float_round(_to_float(line_item.get("quantity")), precision_digits=3)
                    unit_price = float_round(_to_float(line_item.get("unit_price")), precision_digits=3)
                    product_code = self._clean_text(line_item.get("product_code"))
                    description = self._clean_text(line_item.get("description"))
                    unit_name = self._normalize_uom_name(line_item.get("unit"))

                    _logger.info(
                        "[DocAI] Ligne #%s parse -> code='%s' description='%s' qty=%s unit_price=%s amount=%s unit='%s'",
                        idx, product_code, description, qty, unit_price, amount, unit_name
                    )

                    is_product_line = self._docai_is_product_line(line_item)
                    _logger.info("[DocAI] Ligne #%s is_product_line=%s", idx, is_product_line)

                    # -----------------------------------------------------
                    # LIGNE PRODUIT
                    # -----------------------------------------------------
                    if is_product_line:
                        if amount <= 0 and qty > 0 and unit_price > 0:
                            amount = float_round(qty * unit_price, precision_digits=3)
                            _logger.info("[DocAI] Ligne #%s recalcul amount=%s", idx, amount)

                        if unit_price <= 0 and qty > 0 and amount > 0:
                            unit_price = float_round(amount / qty, precision_digits=3)
                            _logger.info("[DocAI] Ligne #%s recalcul unit_price=%s", idx, unit_price)

                        if qty <= 0:
                            qty = 1.0
                            _logger.info("[DocAI] Ligne #%s qty forcée à 1.0", idx)

                        product = self._docai_find_product(
                            move,
                            line_item,
                            unknown_product_id=unknown_product_id,
                        )

                        _logger.info("[DocAI] Ligne #%s produit retenu=%s", idx, product.display_name if product else "AUCUN")

                        uom = False
                        if unit_name:
                            uom = self.env["uom.uom"].search([
                                "|",
                                ("name", "ilike", unit_name),
                                ("name", "=", unit_name),
                            ], limit=1)
                            _logger.info("[DocAI] Ligne #%s UoM recherchée='%s' -> %s", idx, unit_name, uom.name if uom else "NON TROUVÉE")

                        product_uom_id = False
                        if product and uom:
                            if product.uom_id.category_id == uom.category_id:
                                product_uom_id = uom.id
                                _logger.info("[DocAI] Ligne #%s UoM compatible -> %s", idx, uom.name)
                            else:
                                product_uom_id = product.uom_id.id
                                _logger.info(
                                    "[DocAI] Ligne #%s UoM incompatible '%s', on garde UoM produit='%s'",
                                    idx, uom.name, product.uom_id.name
                                )
                        elif product:
                            product_uom_id = product.uom_id.id
                            _logger.info("[DocAI] Ligne #%s UoM produit par défaut -> %s", idx, product.uom_id.name)

                        display_name = product.name if product else self._docai_prepare_product_name(line_item)
                        account_id = self._docai_get_expense_account(move, product)

                        _logger.info(
                            "[DocAI] Ligne #%s display_name='%s' account_id=%s product_uom_id=%s",
                            idx, display_name, account_id, product_uom_id
                        )

                        if not account_id:
                            raise UserError(
                                _("Aucun compte de charge trouvé pour la ligne %s : %s")
                                % (idx, display_name)
                            )

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

                        _logger.info("[DocAI] Ligne #%s invoice_line_vals=%s", idx, line_vals)
                        new_lines.append((0, 0, line_vals))
                        continue

                    # -----------------------------------------------------
                    # LIGNE COMMENTAIRE
                    # -----------------------------------------------------
                    comment_label = self._docai_prepare_comment_label(line_item)
                    if amount <= 0:
                        note_vals = {
                            "display_type": "line_note",
                            "name": comment_label,
                        }
                        _logger.info("[DocAI] Ligne #%s commentaire -> %s", idx, note_vals)
                        new_lines.append((0, 0, note_vals))
                        continue

                    _logger.info("[DocAI] Ligne #%s ignorée sans action", idx)

                # ---------------------------------------------------------
                # Écriture finale
                # ---------------------------------------------------------
                _logger.info("[DocAI] Nombre total de lignes préparées=%s", len(new_lines))

                if new_lines:
                    write_vals = {"invoice_line_ids": [(5, 0, 0)] + new_lines}
                    _logger.info("[DocAI] move.write lignes ...")
                    move.write(write_vals)
                    _logger.info("[DocAI] ✅ Lignes écrites sur facture id=%s", move.id)
                else:
                    _logger.warning("[DocAI] ⚠️ Aucune ligne préparée pour facture id=%s", move.id)

                _logger.info("[DocAI] ---- Fin traitement facture id=%s ----", move.id)

            except Exception as e:
                _logger.exception("[DocAI] ❌ Erreur pendant action_docai_scan_json sur facture id=%s", move.id)
                raise UserError(_("Erreur DocAI sur la facture %s : %s") % (move.display_name, e))

    # ---------------------------------------------------------------------
    # CRON
    # ---------------------------------------------------------------------
    @api.model
    def cron_docai_parse_json(self):
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
                _logger.info("[DocAI JSON CRON] ✅ Facture %s traitée", move.id)
            except Exception as e:
                _logger.exception("[DocAI JSON CRON] ❌ Erreur facture %s", move.id)
                _logger.error("[DocAI JSON CRON] Détail : %s", e)
                continue
