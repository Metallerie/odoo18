# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime

from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    docai_json_raw = fields.Text("JSON complet DocAI", readonly=True)
    docai_json = fields.Text("JSON simplifié DocAI", readonly=True)
    docai_analyzed = fields.Boolean("Analysée par DocAI", default=False, readonly=True)

    # -------------------------------------------------------------------------
    # OUTILS GÉNÉRAUX
    # -------------------------------------------------------------------------
    def _load_docai_json_data(self):
        self.ensure_one()

        if not self.docai_json:
            raise UserError(_("Aucun JSON DocAI n'est disponible sur cette facture."))

        try:
            data = json.loads(self.docai_json)
        except Exception as e:
            _logger.error("[DocAI] JSON invalide pour move %s : %s", self.id, e)
            raise UserError(_("Le JSON DocAI est invalide."))

        if not isinstance(data, dict):
            raise UserError(_("Le JSON DocAI doit être un objet JSON."))

        return data

    def _parse_docai_date(self, value):
        """Convertit une date texte en date Odoo."""
        if not value:
            return False

        value = str(value).strip()
        if not value:
            return False

        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d.%m.%Y",
            "%Y/%m/%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).date()
            except Exception:
                continue

        _logger.warning("[DocAI] Date non reconnue pour move %s : %s", self.id, value)
        return False

    def _clean_vat_value(self, value):
        """Nettoie TVA / SIRET / SIREN pour comparaison."""
        if not value:
            return ""
        return "".join(str(value).strip().upper().split())

    def _normalize_search_text(self, value):
        """Normalise un texte pour recherche souple."""
        if not value:
            return ""

        value = str(value).lower().strip()

        for char in ['"', "'", "\n", "\r", "\t", ",", ";", ":", ".", "(", ")", "-", "_", "/", "\\", "[", "]", "{", "}"]:
            value = value.replace(char, " ")

        return " ".join(value.split())

    # -------------------------------------------------------------------------
    # LECTURE HEADER JSON
    # -------------------------------------------------------------------------
    def _get_docai_header_values(self, data):
        self.ensure_one()

        return {
            "supplier_name": (data.get("supplier_name") or "").strip(),
            "supplier_vat": (data.get("supplier_vat") or "").strip(),
            "supplier_siret": (
                data.get("supplier_siret")
                or data.get("supplier_registration")
                or data.get("supplier_siren")
                or ""
            ).strip(),
            "invoice_number": (
                data.get("invoice_number")
                or data.get("invoice_id")
                or ""
            ).strip(),
            "invoice_date": self._parse_docai_date(data.get("invoice_date")),
            "due_date": self._parse_docai_date(
                data.get("due_date") or data.get("invoice_date_due")
            ),
            "currency": (data.get("currency") or "").strip(),
            "payment_reference": (data.get("payment_reference") or "").strip(),
        }

    # -------------------------------------------------------------------------
    # RECHERCHE FOURNISSEUR INVERSE
    # -------------------------------------------------------------------------
    def _find_partner_by_reverse_search_in_docai_json(self, data):
        """
        Si la recherche directe échoue :
        on cherche un fournisseur Odoo dont le nom apparaît dans docai_json.
        """
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()

        try:
            json_text = self._normalize_search_text(json.dumps(data, ensure_ascii=False))
        except Exception as e:
            _logger.warning("[DocAI] Impossible de sérialiser le JSON pour recherche inverse sur move %s : %s", self.id, e)
            return False

        if not json_text:
            return False

        partners = Partner.search([
            ("name", "!=", False),
            ("is_company", "=", True),
        ])

        exact_matches = []
        partial_matches = []

        for partner in partners:
            partner_name = self._normalize_search_text(partner.name)

            if not partner_name:
                continue

            if len(partner_name) < 4:
                continue

            if partner_name in json_text:
                exact_matches.append(partner)
                continue

            # recherche plus souple mot à mot
            partner_words = [w for w in partner_name.split() if len(w) >= 4]
            if partner_words and all(word in json_text for word in partner_words):
                partial_matches.append(partner)

        if len(exact_matches) == 1:
            _logger.info(
                "[DocAI] Fournisseur trouvé par recherche inverse exacte pour move %s : %s",
                self.id,
                exact_matches[0].display_name,
            )
            return exact_matches[0]

        if len(exact_matches) > 1:
            _logger.warning(
                "[DocAI] Plusieurs fournisseurs trouvés par recherche inverse exacte pour move %s : %s",
                self.id,
                ", ".join(exact_matches.mapped("display_name")),
            )
            return exact_matches[0]

        if len(partial_matches) == 1:
            _logger.info(
                "[DocAI] Fournisseur trouvé par recherche inverse partielle pour move %s : %s",
                self.id,
                partial_matches[0].display_name,
            )
            return partial_matches[0]

        if len(partial_matches) > 1:
            _logger.warning(
                "[DocAI] Plusieurs fournisseurs trouvés par recherche inverse partielle pour move %s : %s",
                self.id,
                ", ".join(partial_matches.mapped("display_name")),
            )
            return partial_matches[0]

        return False

    # -------------------------------------------------------------------------
    # RECHERCHE FOURNISSEUR DIRECTE + INVERSE
    # -------------------------------------------------------------------------
    def _find_partner_from_docai_header(self, header_vals, data=None):
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()

        supplier_name = header_vals.get("supplier_name") or ""
        supplier_vat = self._clean_vat_value(header_vals.get("supplier_vat"))
        supplier_siret = self._clean_vat_value(header_vals.get("supplier_siret"))

        partner = False

        # 1. Recherche par TVA
        if supplier_vat:
            partners = Partner.search([("vat", "!=", False)])
            partner = partners.filtered(
                lambda p: self._clean_vat_value(p.vat) == supplier_vat
            )[:1]

            if partner:
                _logger.info("[DocAI] Fournisseur trouvé par TVA pour move %s : %s", self.id, partner.display_name)

        # 2. Recherche par registre société
        if not partner and supplier_siret:
            partners = Partner.search([("company_registry", "!=", False)])
            partner = partners.filtered(
                lambda p: self._clean_vat_value(p.company_registry) == supplier_siret
            )[:1]

            if partner:
                _logger.info("[DocAI] Fournisseur trouvé par company_registry pour move %s : %s", self.id, partner.display_name)

        # 3. Fallback sur VAT si le SIRET est stocké dedans
        if not partner and supplier_siret:
            partners = Partner.search([("vat", "!=", False)])
            partner = partners.filtered(
                lambda p: self._clean_vat_value(p.vat) == supplier_siret
            )[:1]

            if partner:
                _logger.info("[DocAI] Fournisseur trouvé par SIRET dans VAT pour move %s : %s", self.id, partner.display_name)

        # 4. Recherche simple par nom
        if not partner and supplier_name:
            partner = Partner.search([("name", "ilike", supplier_name)], limit=1)

            if partner:
                _logger.info("[DocAI] Fournisseur trouvé par nom direct pour move %s : %s", self.id, partner.display_name)

        # 5. Recherche inverse Odoo -> JSON
        if not partner and data:
            partner = self._find_partner_by_reverse_search_in_docai_json(data)

        if not partner:
            _logger.warning(
                "[DocAI] Fournisseur non trouvé pour move %s | name=%s | vat=%s | siret=%s",
                self.id,
                supplier_name,
                supplier_vat,
                supplier_siret,
            )

        return partner

    # -------------------------------------------------------------------------
    # DEVISE
    # -------------------------------------------------------------------------
    def _find_currency_from_docai_header(self, header_vals):
        self.ensure_one()
        Currency = self.env["res.currency"].sudo()

        currency_value = header_vals.get("currency") or ""
        if not currency_value:
            return False

        if currency_value == "€":
            currency = Currency.search([("name", "=", "EUR")], limit=1)
            if currency:
                return currency

        currency = Currency.search([("name", "=", currency_value.upper())], limit=1)
        if currency:
            return currency

        currency = Currency.search([("symbol", "=", currency_value)], limit=1)
        return currency or False

    # -------------------------------------------------------------------------
    # AIDE MISE À JOUR CHAMPS
    # -------------------------------------------------------------------------
    def _set_header_value(self, vals, field_name, new_value, force_update=False):
        """
        Ajoute une valeur dans vals :
        - si le champ est vide
        - ou si force_update=True
        """
        self.ensure_one()

        if new_value in (False, None, "", []):
            return

        current_value = self[field_name]

        if force_update or not current_value:
            vals[field_name] = new_value

    # -------------------------------------------------------------------------
    # PRÉPARATION DES VALEURS À ÉCRIRE
    # -------------------------------------------------------------------------
    def _prepare_move_header_vals_from_docai(self, data, force_update=False):
        self.ensure_one()

        header_vals = self._get_docai_header_values(data)
        vals = {}

        partner = self._find_partner_from_docai_header(header_vals, data=data)
        currency = self._find_currency_from_docai_header(header_vals)

        if partner:
            self._set_header_value(vals, "partner_id", partner.id, force_update=force_update)

        if header_vals["invoice_number"]:
            self._set_header_value(vals, "ref", header_vals["invoice_number"], force_update=force_update)

        if header_vals["invoice_date"]:
            self._set_header_value(vals, "invoice_date", header_vals["invoice_date"], force_update=force_update)

        if header_vals["due_date"]:
            self._set_header_value(vals, "invoice_date_due", header_vals["due_date"], force_update=force_update)

        if header_vals["payment_reference"]:
            self._set_header_value(vals, "payment_reference", header_vals["payment_reference"], force_update=force_update)

        if currency:
            if force_update or self.currency_id != currency:
                vals["currency_id"] = currency.id

        return vals, header_vals

    # -------------------------------------------------------------------------
    # ACTION PRINCIPALE
    # -------------------------------------------------------------------------
    def action_docai_scan_json(self):
        """
        Remplit uniquement les champs vides.
        """
        for move in self:
            if move.move_type not in ("in_invoice", "in_refund"):
                _logger.info(
                    "[DocAI] Move %s ignoré : type %s non géré",
                    move.id,
                    move.move_type,
                )
                continue

            data = move._load_docai_json_data()
            vals, header_vals = move._prepare_move_header_vals_from_docai(
                data,
                force_update=False,
            )

            if vals:
                move.write(vals)
                _logger.info("[DocAI] En-tête mis à jour pour move %s : %s", move.id, vals)
            else:
                _logger.info("[DocAI] Aucun champ vide à remplir pour move %s", move.id)

            _logger.info(
                "[DocAI] Header lu pour move %s | supplier=%s | invoice=%s | date=%s | due=%s | currency=%s",
                move.id,
                header_vals.get("supplier_name"),
                header_vals.get("invoice_number"),
                header_vals.get("invoice_date"),
                header_vals.get("due_date"),
                header_vals.get("currency"),
            )

    def action_docai_rescan_json(self):
        """
        Force la mise à jour même si les champs sont déjà remplis.
        """
        for move in self:
            if move.move_type not in ("in_invoice", "in_refund"):
                _logger.info(
                    "[DocAI] Move %s ignoré : type %s non géré",
                    move.id,
                    move.move_type,
                )
                continue

            data = move._load_docai_json_data()
            vals, header_vals = move._prepare_move_header_vals_from_docai(
                data,
                force_update=True,
            )

            if vals:
                move.write(vals)
                _logger.info("[DocAI] En-tête forcé pour move %s : %s", move.id, vals)
            else:
                _logger.info("[DocAI] Rien à forcer pour move %s", move.id)

            _logger.info(
                "[DocAI] Header relu pour move %s | supplier=%s | invoice=%s | date=%s | due=%s | currency=%s",
                move.id,
                header_vals.get("supplier_name"),
                header_vals.get("invoice_number"),
                header_vals.get("invoice_date"),
                header_vals.get("due_date"),
                header_vals.get("currency"),
            )
