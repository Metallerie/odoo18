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
    # enlever espaces et caractères non numériques usuels (sauf . , -)
    s = str(val).strip()
    s = s.replace(" ", "").replace("\u00A0", "")  # espaces insécables
    # convertir virgule décimale en point
    s = s.replace(",", ".")
    # garder chiffres . -
    m = re.findall(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return 0.0
    try:
        return float(m[0])
    except Exception:
        return 0.0


def _norm_type(t):
    """'line_item/description' -> 'description' ; 'description' -> 'description'"""
    if not t:
        return ""
    return str(t).split("/")[-1]


class AccountMove(models.Model):
    _inherit = "account.move"

    def _docai_entities(self, data):
        """Retourne la liste des entities depuis un dict JSON."""
        # data attendu: {"entities": [...]}
        ents = data.get("entities")
        return ents if isinstance(ents, list) else []

    def _docai_first_map(self, entities):
        """Map simple type_ -> mentionText (1er match)."""
        m = {}
        for ent in entities:
            t = ent.get("type_")
            txt = ent.get("mentionText")
            if t and txt and t not in m:
                m[t] = txt
        return m

    def _find_partner_from_docai(self, ent_map):
        """Essaie de retrouver le partenaire par SIREN/VAT ou par nom."""
        Partner = self.env["res.partner"]
        # Certains jeux renvoient supplier_registration (SIREN) ou supplier_tax_id (FR…)
        vat = ent_map.get("supplier_registration") or ent_map.get("supplier_tax_id")
        if vat:
            p = Partner.search([("vat", "=", vat)], limit=1)
            if p:
                return p
        name = ent_map.get("supplier_name")
        if name:
            p = Partner.search([("name", "ilike", name)], limit=1)
            if p:
                return p
        return None

    def _find_tax_from_docai(self, ent_map):
        """Retourne une taxe d'achat correspondant au taux détecté (ex: 20%)."""
        rate_txt = None
        # Cas 1: 'vat' peut contenir le taux (ex mentionText '20%')
        # Cas 2: sous-propriété 'vat/tax_rate' renvoyée mais non mappée ici
        # On essaie aussi 'total_tax_amount' / 'vat/tax_amount' -> si pas de taux, on ne met pas la taxe
        # On parcourt tout pour trouver un taux exploitable
        for k, v in ent_map.items():
            if k in ("vat", "vat/tax_rate") or "tax_rate" in k:
                rate_txt = v
                break
        if not rate_txt:
            return None
        # extraire nombre
        rate = _to_float(rate_txt)
        if rate > 1.0:  # '20' ou '20%' -> 20%
            pass
        elif 0.0 < rate < 1.0:  # ex 0.2 -> 20
            rate = rate * 100.0
        else:
            return None
        # chercher une taxe achat pour la société courante
        Tax = self.env["account.tax"].with_context(active_test=False)
        company = self.env.company
        tax = Tax.search([
            ("company_id", "=", company.id),
            ("type_tax_use", "in", ["purchase", "none"]),
            ("amount", "=", rate),
            ("price_include", "=", False),
            ("amount_type", "=", "percent"),
        ], limit=1)
        return tax or None

    # -------------------------------------------------------------------------
    # Action principale : lecture du JSON brut Document AI
    # -------------------------------------------------------------------------
    def action_docai_scan_json(self):
        """
        Lit le champ docai_json (JSON brut DocAI avec entities/properties)
        et met à jour les infos de la facture + lignes
        """
        for move in self:
            if not move.docai_json:
                raise UserError(_("Aucun JSON DocAI trouvé sur cette facture."))

            try:
                data = json.loads(move.docai_json)
            except Exception as e:
                raise UserError(_("JSON invalide : %s") % e)

            entities = self._docai_entities(data)
            if not entities:
                _logger.warning(f"⚠️ Facture {move.id} : JSON sans 'entities'")
                continue

            vals = {}
            ent_map = self._docai_first_map(entities)

            # -------- En-tête facture --------
            inv_id = ent_map.get("invoice_id")
            if inv_id:
                vals["ref"] = inv_id

            inv_date = ent_map.get("invoice_date")
            if inv_date:
                # DocAI renvoie souvent 'YYYY-MM-DD' -> Odoo OK
                vals["invoice_date"] = inv_date

            partner = self._find_partner_from_docai(ent_map)
            if partner:
                vals["partner_id"] = partner.id

            # Ne pas écrire amount_total (calculé par Odoo)
            # On laisse les taxes/lignes recalculer le total.

            if vals:
                move.write(vals)
                _logger.info(f"✅ Facture {move.id} entête mise à jour : {vals}")

            # -------- TVA détectée (facultatif) --------
            tax = self._find_tax_from_docai(ent_map)

            # -------- Lignes --------
            # Stratégie 1 : entités de type "line_item" avec properties[]
            line_items = [e for e in entities if e.get("type_") == "line_item"]
            new_lines = []

            if line_items:
                for li in line_items:
                    props = li.get("properties", []) or []
                    # On fabrique un dict clé->val dépouillé du préfixe
                    pmap = {}
                    for p in props:
                        t = _norm_type(p.get("type_"))
                        txt = p.get("mentionText")
                        if t and txt and t not in pmap:
                            pmap[t] = txt

                    name = pmap.get("description") or pmap.get("item_description") or (li.get("mentionText") or "Ligne")
                    qty = _to_float(pmap.get("quantity") or 1.0)
                    unit_price = _to_float(pmap.get("unit_price") or pmap.get("price") or 0.0)
                    amount = _to_float(pmap.get("amount") or pmap.get("line_total") or 0.0)

                    # Si pas d'unit_price mais un amount existe pour qty=1 → prendre amount
                    if unit_price <= 0 and qty > 0 and amount > 0:
                        unit_price = amount / qty

                    line_vals = {
                        "name": name,
                        "quantity": qty if qty > 0 else 1.0,
                        "price_unit": unit_price,
                        # Compte par défaut du journal si dispo (utile pour éviter erreurs)
                        "account_id": move.journal_id.default_account_id.id if move.journal_id.default_account_id else False,
                    }

                    # Ajouter taxe si trouvée
                    if tax:
                        line_vals["tax_ids"] = [(6, 0, [tax.id])]

                    # Essayer d'associer un produit par description (optionnel)
                    if name:
                        product = self.env["product.product"].search([("name", "ilike", name)], limit=1)
                        if product:
                            line_vals["product_id"] = product.id

                    new_lines.append((0, 0, line_vals))

            else:
                # Stratégie 2 (fallback) :
                # Parfois DocAI sort les props "line_item/..." directement comme entities (sans parent).
                # On regroupe grossièrement par "blocs" séquentiels : description -> quantity -> unit_price -> amount
                grouped = []
                buf = {}
                for ent in entities:
                    t = ent.get("type_")
                    if not t or not t.startswith("line_item/"):
                        continue
                    key = _norm_type(t)
                    buf[key] = ent.get("mentionText")
                    # heuristique simple : quand on voit un amount, on clôt la ligne
                    if key in ("amount", "line_total", "total_amount"):
                        grouped.append(buf)
                        buf = {}
                if buf:
                    grouped.append(buf)

                for pmap in grouped:
                    name = pmap.get("description") or "Ligne importée"
                    qty = _to_float(pmap.get("quantity") or 1.0)
                    unit_price = _to_float(pmap.get("unit_price") or pmap.get("price") or 0.0)
                    amount = _to_float(pmap.get("amount") or pmap.get("line_total") or 0.0)
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
                    product = self.env["product.product"].search([("name", "ilike", name)], limit=1)
                    if product:
                        line_vals["product_id"] = product.id
                    new_lines.append((0, 0, line_vals))

            if new_lines:
                # Remplace les lignes existantes par celles détectées
                move.write({"invoice_line_ids": [(5, 0, 0)] + new_lines})
                _logger.info(f"✅ Facture {move.id} : {len(new_lines)} lignes importées depuis DocAI")
            else:
                _logger.warning(f"⚠️ Facture {move.id} : aucune ligne détectée (entities présentes={len(entities)})")

    # -------------------------------------------------------------------------
    # Debug : voir les clés et un échantillon des types
    # -------------------------------------------------------------------------
    def action_docai_debug_json(self):
        for move in self:
            if not move.docai_json:
                raise UserError(_("Aucun JSON DocAI trouvé sur cette facture."))
            try:
                data = json.loads(move.docai_json)
                entities = self._docai_entities(data)
                sample_types = list({e.get("type_") for e in entities if e.get("type_")})[:20]
                raise UserError(_("Clés JSON: %s\nTypes (extrait): %s") % (", ".join(data.keys()), ", ".join(sample_types)))
            except Exception as e:
                raise UserError(_("Erreur parsing JSON : %s") % e)
