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
    # OUTILS JSON
    # -------------------------------------------------------------------------
    def _load_docai_json_data(self):
        self.ensure_one()

        if not self.docai_json:
            raise UserError(_("Aucun JSON DocAI n'est disponible sur cette facture."))

        try:
            data = json.loads(self.docai_json)
        except Exception as e:
            _logger.error("[DocAI] JSON invalide pour account.move %s : %s", self.id, e)
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

        _logger.warning("[DocAI] Date non reconnue : %s", value)
        return False

    def _clean_vat_value(self, value):
        """Nettoie une valeur TVA/SIRET/SIREN pour comparaison."""
        if not value:
            return ""
        return "".join(str(value).strip().upper().split())

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
    # RECHERCHE FOURNISSEUR
    # -------------------------------------------------------------------------
    def _find_partner_from_docai_header(self, header_vals):
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

        # 2. Recherche par registre société / SIRET / SIREN
        if not partner and supplier_siret:
            partners = Partner.search([("company_registry", "!=", False)])
            partner = partners.filtered(
                lambda p: self._clean_vat_value(p.company_registry) == supplier_siret
            )[:1]

        # 3. Fallback large sur VAT au cas où le SIRET y serait stocké
        if not partner and supplier_siret:
            partners = Partner.search([("vat", "!=", False)])
            partner = partners.filtered(
                lambda p: self._clean_vat_value(p.vat) == supplier_siret
            )[:1]

        # 4. Recherche par nom
        if not partner and supplier_name:
            partner = Partner.search([("name", "ilike", supplier_name)], limit=1)

        if partner:
            _logger.info(
                "[DocAI] Fournisseur trouvé pour move %s : %s",
                self.id,
                partner.display_name,
            )
        else:
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

        # Cas symbole euro courant
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
    # PRÉPARATION DES VALEURS À ÉCRIRE
    # -------------------------------------------------------------------------
    def _prepare_move_header_vals_from_docai(self, data):
        self.ensure_one()

        header_vals = self._get_docai_header_values(data)
        vals = {}

        partner = self._find_partner_from_docai_header(header_vals)
        currency = self._find_currency_from_docai_header(header_vals)

        if partner and not self.partner_id:
            vals["partner_id"] = partner.id

        if header_vals["invoice_number"] and not self.ref:
            vals["ref"] = header_vals["invoice_number"]

        if header_vals["invoice_date"] and not self.invoice_date:
            vals["invoice_date"] = header_vals["invoice_date"]

        if header_vals["due_date"] and not self.invoice_date_due:
            vals["invoice_date_due"] = header_vals["due_date"]

        if header_vals["payment_reference"] and not self.payment_reference:
            vals["payment_reference"] = header_vals["payment_reference"]

        if currency and self.currency_id != currency:
            vals["currency_id"] = currency.id

        return vals, header_vals

    # -------------------------------------------------------------------------
    # ACTION PRINCIPALE : SCAN JSON HEADER
    # -------------------------------------------------------------------------
    def action_docai_scan_json(self):
        for move in self:
            if move.move_type not in ("in_invoice", "in_refund"):
                _logger.info(
                    "[DocAI] Move %s ignoré : type %s non géré",
                    move.id,
                    move.move_type,
                )
                continue

            data = move._load_docai_json_data()
            vals, header_vals = move._prepare_move_header_vals_from_docai(data)

            if vals:
                move.write(vals)
                _logger.info(
                    "[DocAI] En-tête mis à jour pour move %s : %s",
                    move.id,
                    vals,
                )
            else:
                _logger.info(
                    "[DocAI] Aucun champ d'en-tête à mettre à jour pour move %s",
                    move.id,
                )

            # Petit log utile pour debug
            _logger.info(
                "[DocAI] Header lu pour move %s | supplier=%s | invoice=%s | date=%s | due=%s | currency=%s",
                move.id,
                header_vals.get("supplier_name"),
                header_vals.get("invoice_number"),
                header_vals.get("invoice_date"),
                header_vals.get("due_date"),
                header_vals.get("currency"),
            )
