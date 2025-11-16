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
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12, "decembre": 12, "déc": 12, "dec": 12,
}


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
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(" ", "").replace("\u00A0", "").replace(",", ".")
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
        m = {}
        for ent in entities:
            t = ent.get("type") or ent.get("type_")
            txt = ent.get("mentionText")
            if t and txt and t not in m:
                m[t] = ent.get("normalizedValue", txt)
        return m

    def _find_tax_from_docai(self, ent_map):
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
    # Action principale
    # -------------------------------------------------------------------------
    def action_docai_scan_json(self):
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

            # Fournisseur : on NE remplace PAS un vrai fournisseur par l'inconnu
            unknown_supplier_id = int(
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("docai_ai.unknown_supplier_id", 0)
            ) or False

            supplier = False
            if ent_map.get("supplier_name"):
                supplier_name = str(ent_map["supplier_name"]).strip()

                # 1) on cherche un vrai fournisseur
                supplier = self.env["res.partner"].search(
                    [("name", "ilike", supplier_name)],
                    limit=1,
                )

                # 2) si rien trouvé, on prend l'inconnu
                if not supplier and unknown_supplier_id:
                    supplier = self.env["res.partner"].browse(unknown_supplier_id)

            # 3) écriture : seulement si
            #    - aucun fournisseur sur la facture, ou
            #    - le fournisseur actuel est déjà "inconnu"
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

            for li in line_items:
                props = li.get("properties", []) or []
                pmap = {}
                for p in props:
                    t = _norm_type(p.get("type") or p.get("type_"))
                    txt = p.get("mentionText")
                    if t and txt and t not in pmap:
                        pmap[t] = txt

                name = pmap.get("description") or "Ligne"

                qty = _to_float(pmap.get("quantity") or 1.0)
                unit_price = _to_float(pmap.get("unit_price") or 0.0)
                amount = _to_float(pmap.get("amount") or 0.0)

                qty = float_round(qty, precision_digits=3)
                unit_price = float_round(unit_price, precision_digits=3)
                amount = float_round(amount, precision_digits=3)

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
                # Recherche produit : priorité à la réf fournisseur pour ce partenaire
                # -----------------------------------------------------------------
                unknown_product_id = int(
                    self.env["ir.config_parameter"]
                    .sudo()
                    .get_param("docai_ai.unknown_product_id", 0)
                ) or False

                product = None
                partner = move.partner_id  # normalement CCL ici

                if pmap.get("product_code"):
                    code = pmap["product_code"].strip().upper()

                    # 1) Référence fournisseur (product.supplierinfo.product_code)
                    si_domain = [("product_code", "=", code)]
                    if partner:
                        si_domain.append(("name", "=", partner.id))
                    supplierinfo = self.env["product.supplierinfo"].search(
                        si_domain, limit=1
                    )
                    if supplierinfo and supplierinfo.product_tmpl_id:
                        product = supplierinfo.product_tmpl_id.product_variant_id

                    # 2) Code interne (default_code)
                    if not product:
                        product = self.env["product.product"].search(
                            [("default_code", "=", code)],
                            limit=1,
                        )
                    if not product:
                        product = self.env["product.product"].search(
                            [("default_code", "ilike", code)],
                            limit=1,
                        )

                # 3) Recherche par nom de ligne
                if not product and name:
                    product = self.env["product.product"].search(
                        [("name", "ilike", name)],
                        limit=1,
                    )

                # 4) Produit inconnu seulement si rien trouvé
                if not product and unknown_product_id:
                    product = self.env["product.product"].browse(unknown_product_id)
                    _logger.info(
                        "⚠️ Aucun produit trouvé, utilisation du produit inconnu pour %s",
                        name,
                    )

                # -----------------------------------------------------------------
                # UoM
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

                display_name = f"{product.name} / {name}" if product else name

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
                    "product_uom_id": uom.id if uom else False,
                    "account_id": account_id,
                }
                if tax:
                    line_vals["tax_ids"] = [(6, 0, [tax.id])]

                new_lines.append((0, 0, line_vals))

            if new_lines:
                move.write({"invoice_line_ids": [(5, 0, 0)] + new_lines})
                move._compute_amount()
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
