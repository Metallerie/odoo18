# -*- coding: utf-8 -*-
import json
import logging
import re
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _to_float(val):
    """Convertit '12,50' -> 12.50 ; ' 3 974 ' -> 3974.0 ; None -> 0.0"""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    s = s.replace(" ", "").replace("\u00A0", "")  # espaces insécables
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
                m[t] = txt
        return m

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
                vals["invoice_date"] = ent_map["invoice_date"]

            if vals:
                move.write(vals)
                print(f"✅ Facture {move.id} mise à jour avec {vals}")

            # TVA détectée
            tax = self._find_tax_from_docai(ent_map)
            if tax:
                print(f"🧾 Taxe trouvée : {tax.name} ({tax.amount}%)")

            # Lignes
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
                    print(f"   - {e.get('type') or e.get('type_')} = {e.get('mentionText')}")
            except Exception as e:
                print(f"❌ Erreur parsing JSON : {e}")
                raise UserError(_("Erreur parsing JSON : %s") % e)
