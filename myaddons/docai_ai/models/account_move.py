# -*- coding: utf-8 -*-
import json
import logging
import re
from datetime import datetime
from odoo import models, fields, _
from odoo.exceptions import UserError

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
    """Retourne 'YYYY-MM-DD' à partir de formats FR/ISO ou normalizedValue."""
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
    s = str(val).strip()
    s = s.replace(" ", "").replace("\u00A0", "")
    s = s.replace(",", ".")
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
                if ent.get("normalizedValue"):
                    m[t] = ent["normalizedValue"]
                else:
                    m[t] = txt
        return m

    def _find_tax_from_docai(self, ent_map):
        """Trouve un objet account.tax à partir des entités DocAI (TVA)."""
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
                    if tax_rate > 1 and tax_rate <= 100:
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

            print(f"🔎 Facture {move.id} → lecture JSON…")
            try:
                data = json.loads(move.docai_json)
            except Exception as e:
                print(f"❌ Erreur JSON : {e}")
                raise UserError(_("JSON invalide : %s") % e)

            entities = self._docai_entities(data)
            print(f"📄 {len(entities)} entités détectées")
            if not entities:
                _logger.warning(f"⚠️ Facture {move.id} : JSON sans 'entities'")
                continue

            ent_map = self._docai_first_map(entities)
            print(f"📌 Mapping entête extrait : {ent_map}")

            vals = {}
            if ent_map.get("invoice_id"):
                vals["ref"] = ent_map["invoice_id"]
            if ent_map.get("invoice_date"):
                iso_date = _parse_date_any(ent_map["invoice_date"])
                if iso_date:
                    vals["invoice_date"] = iso_date
                else:
                    _logger.warning(f"Facture {move.id}: date illisible '{ent_map['invoice_date']}' — inchangée")

            if vals:
                move.write(vals)
                print(f"✅ Facture {move.id} mise à jour avec {vals}")

            tax = self._find_tax_from_docai(ent_map)
            if tax:
                print(f"🧾 Taxe trouvée : {tax.name} ({tax.amount}%)")

            line_items = [e for e in entities if (e.get("type") or e.get("type_")) == "line_item"]
            new_lines = []
            print(f"🛠 Analyse des lignes : {len(line_items)} candidates")

            for li in line_items:
                props = li.get("properties", []) or []
                pmap = {}
                for p in props:
                    t = _norm_type(p.get("type") or p.get("type_"))
                    txt = p.get("mentionText")
                    if t and txt and t not in pmap:
                        pmap[t] = txt
                print(f"   ➡️ Ligne brute : {pmap}")

                name = pmap.get("description") or "Ligne"
                qty = _to_float(pmap.get("quantity") or 1.0)
                unit_price = _to_float(pmap.get("unit_price") or 0.0)
                amount = _to_float(pmap.get("amount") or 0.0)
                if unit_price <= 0 and qty > 0 and amount > 0:
                    unit_price = amount / qty

                line_vals = {
                    "name": name,
                    "quantity": qty if qty > 0 else 1.0,
                    "price_unit": unit_price,
                    "account_id": move.journal_id.default_account_id.id if move.journal_id.default_account_id else False,
                }
                if tax:
                    line_vals["tax_ids"] = [(6, 0, [tax.id])]
                new_lines.append((0, 0, line_vals))

            if new_lines:
                move.write({"invoice_line_ids": [(5, 0, 0)] + new_lines})
                print(f"✅ {len(new_lines)} lignes importées pour facture {move.id}")
            else:
                print(f"⚠️ Aucune ligne détectée pour facture {move.id}")

    def action_docai_debug_json(self):
        for move in self:
            if not move.docai_json:
                raise UserError(_("Aucun JSON DocAI trouvé sur cette facture."))
            try:
                data = json.loads(move.docai_json)
                entities = self._docai_entities(data)
                print(f"🔍 DEBUG JSON Facture {move.id} : {len(entities)} entités")
                for e in entities[:10]:
                    print(f"   - {e.get('type') or e.get('type_')} = {e.get('mentionText')} (normalized={e.get('normalizedValue')})")
            except Exception as e:
                print(f"❌ Erreur parsing JSON : {e}")
                raise UserError(_("Erreur parsing JSON : %s") % e)
