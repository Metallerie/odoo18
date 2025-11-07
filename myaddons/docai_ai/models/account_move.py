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
    "octobre": 10, "oct": 10,
    "novembre": 11, "nov": 11,
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
        d_tok, m_tok, y_tok = tokens[i], tokens[i+1], tokens[i+2]
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
        tax = self.env["account.tax"].search([
            ("amount", "=", tax_rate),
            ("type_tax_use", "=", "purchase")
        ], limit=1)
        return tax or False

    def action_docai_scan_json(self):
        for move in self:
            if not move.docai_json:
                raise UserError(_("Aucun JSON DocAI trouvé sur cette facture."))

            _logger.info(f"🔎 Analyse JSON pour facture {move.id} ({move.name or ''})")
            try:
                data = json.loads(move.docai_json)
            except Exception as e:
                raise UserError(_("JSON invalide : %s") % e)

            entities = self._docai_entities(data)
            if not entities:
                _logger.warning(f"[DocAI] Facture {move.id} : JSON sans 'entities'")
                continue

            ent_map = self._docai_first_map(entities)
            vals = {}

            if ent_map.get("invoice_id"):
                vals["ref"] = ent_map["invoice_id"]
            if ent_map.get("invoice_date"):
                iso_date = _parse_date_any(ent_map["invoice_date"])
                if iso_date:
                    vals["invoice_date"] = iso_date

            if ent_map.get("supplier_name"):
                supplier = self.env["res.partner"].search([
                    ("name", "ilike", ent_map["supplier_name"])
                ], limit=1)
                if not supplier:
                    supplier = self.env["res.partner"].create({
                        "name": ent_map["supplier_name"],
                        "supplier_rank": 1
                    })
                vals["partner_id"] = supplier.id

            if vals:
                move.write(vals)
                _logger.info(f"✅ Facture {move.id} mise à jour avec {vals}")

            tax = self._find_tax_from_docai(ent_map)
            if tax:
                _logger.info(f"🧾 Taxe détectée : {tax.name} ({tax.amount}%)")

            line_items = [e for e in entities if (e.get("type") or e.get("type_")) == "line_item"]
            new_lines = []
            for li in line_items:
                props = li.get("properties", []) or []
                pmap = {}
                for p in props:
                    t = _norm_type(p.get("type") or p.get("type_"))
                    txt = p.get("mentionText")
                    if t and txt and t not in pmap:
                        pmap[t] = txt

                name = pmap.get("description") or "Ligne"
                qty = float_round(_to_float(pmap.get("quantity") or 1.0), precision_digits=3)
                unit_price = float_round(_to_float(pmap.get("unit_price") or 0.0), precision_digits=3)
                amount = float_round(_to_float(pmap.get("amount") or 0.0), precision_digits=3)
                if unit_price <= 0 and qty > 0 and amount > 0:
                    unit_price = amount / qty

                product = None
                if pmap.get("product_code"):
                    product = self.env["product.product"].search([
                        ("default_code", "=", pmap["product_code"])
                    ], limit=1)
                if not product and name:
                    product = self.env["product.product"].search([
                        ("name", "ilike", name)
                    ], limit=1)

                uom = None
                if pmap.get("unit") or pmap.get("uom"):
                    uom_name = (


    # -------------------------------------------------------------------------
    # CRON : Analyse automatique des JSON DocAI existants
    # -------------------------------------------------------------------------
    @api.model
    def cron_docai_parse_json(self):
        moves = self.env["account.move"].search([
            ("move_type", "=", "in_invoice"),
            ("state", "=", "draft"),
            ("docai_json", "!=", False),
            ("invoice_line_ids", "=", False),
            ("amount_total", "=", 0),
        ], limit=10)

        _logger.info(f"[DocAI JSON CRON] {len(moves)} factures à interpréter")

        for move in moves:
            try:
                move.action_docai_scan_json()
                _logger.info(f"✅ Facture {move.name or move.id} mise à jour via JSON")
            except Exception as e:
                _logger.error(f"❌ Erreur JSON Facture {move.id}: {e}")
                continue
