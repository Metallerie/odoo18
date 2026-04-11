# -*- coding: utf-8 -*-

import json
import logging
import re
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
        if not value:
            return ""
        return "".join(str(value).strip().upper().split())

    def _clean_digits_only(self, value):
        if not value:
            return ""
        return re.sub(r"\D", "", str(value))

    def _normalize_search_text(self, value):
        if not value:
            return ""

        value = str(value).lower().strip()

        for char in ['"', "'", "\n", "\r", "\t", ",", ";", ":", ".", "(", ")", "-", "_", "/", "\\", "[", "]", "{", "}"]:
            value = value.replace(char, " ")

        return " ".join(value.split())

    def _normalize_company_registry(self, value):
        """
        Normalise SIRET / SIREN :
        - garde uniquement les chiffres
        - retourne 14 chiffres si SIRET
        - retourne 9 chiffres si SIREN
        """
        digits = self._clean_digits_only(value)

        if len(digits) >= 14:
            return digits[:14]

        if len(digits) == 9:
            return digits

        return digits

    def _is_placeholder_supplier_name(self, value):
        name = self._normalize_search_text(value)
        placeholders = {
            "vos contacts",
            "contact",
            "contacts",
            "service client",
            "facturation",
            "relation client",
            "informations",
        }
        return name in placeholders

    # -------------------------------------------------------------------------
    # LECTURE HEADER JSON
    # -------------------------------------------------------------------------
    def _get_docai_header_values(self, data):
        self.ensure_one()

        return {
            "supplier_name": (data.get("supplier_name") or "").strip(),
            "supplier_vat": (
                data.get("supplier_vat")
                or data.get("supplier_tax_id")
                or ""
            ).strip(),
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
            "payment_reference": (
                data.get("payment_reference")
                or data.get("supplier_payment_ref")
                or ""
            ).strip(),
        }

    # -------------------------------------------------------------------------
    # FOURNISSEUR INCONNU / DIVERS
    # -------------------------------------------------------------------------
    def _get_unknown_supplier_partner(self):
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()

        partner = Partner.search([
            ("name", "=", "Fournisseur inconnu")
        ], limit=1)

        if partner:
            return partner

        partner = Partner.search([
            ("name", "=", "Divers")
        ], limit=1)

        if partner:
            return partner

        partner = Partner.create({
            "name": "Fournisseur inconnu",
            "supplier_rank": 1,
            "company_type": "company",
        })

        _logger.warning(
            "[DocAI] Création automatique du partenaire fournisseur par défaut : %s",
            partner.display_name,
        )

        return partner

    # -------------------------------------------------------------------------
    # RECHERCHE FOURNISSEUR
    # -------------------------------------------------------------------------
    def _find_partner_from_docai_header(self, header_vals, data=None):
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()

        supplier_name = (header_vals.get("supplier_name") or "").strip()
        supplier_vat = self._clean_vat_value(header_vals.get("supplier_vat"))
        supplier_registry = self._normalize_company_registry(header_vals.get("supplier_siret"))

        partner = False

        _logger.info(
            "[DocAI] Recherche fournisseur move %s | supplier_name=%s | supplier_vat=%s | supplier_registry=%s",
            self.id, supplier_name, supplier_vat, supplier_registry
        )

        # -----------------------------------------------------------------
        # 1) TVA exacte sur vat
        # -----------------------------------------------------------------
        if supplier_vat and len(supplier_vat) >= 8:
            partners = Partner.search([("vat", "!=", False)])
            partner = partners.filtered(
                lambda p: self._clean_vat_value(p.vat) == supplier_vat
            )[:1]

            if partner:
                _logger.info(
                    "[DocAI] Fournisseur trouvé par TVA pour move %s : %s",
                    self.id,
                    partner.display_name,
                )

        # -----------------------------------------------------------------
        # 2) SIRET/SIREN exact sur company_registry
        # -----------------------------------------------------------------
        if not partner and supplier_registry:
            partners = Partner.search([("company_registry", "!=", False)])
            partner = partners.filtered(
                lambda p: self._normalize_company_registry(p.company_registry) == supplier_registry
            )[:1]

            if partner:
                _logger.info(
                    "[DocAI] Fournisseur trouvé par company_registry pour move %s : %s",
                    self.id,
                    partner.display_name,
                )

        # -----------------------------------------------------------------
        # 3) SIRET/SIREN rangé dans VAT
        # -----------------------------------------------------------------
        if not partner and supplier_registry:
            partners = Partner.search([("vat", "!=", False)])
            partner = partners.filtered(
                lambda p: self._clean_digits_only(p.vat) == supplier_registry
            )[:1]

            if partner:
                _logger.info(
                    "[DocAI] Fournisseur trouvé par SIRET/SIREN dans VAT pour move %s : %s",
                    self.id,
                    partner.display_name,
                )

        # -----------------------------------------------------------------
        # 4) TVA rangée dans company_registry
        # -----------------------------------------------------------------
        if not partner and supplier_vat and len(supplier_vat) >= 8:
            partners = Partner.search([("company_registry", "!=", False)])
            partner = partners.filtered(
                lambda p: self._clean_vat_value(p.company_registry) == supplier_vat
            )[:1]

            if partner:
                _logger.info(
                    "[DocAI] Fournisseur trouvé par TVA dans company_registry pour move %s : %s",
                    self.id,
                    partner.display_name,
                )

        # -----------------------------------------------------------------
        # 5) Recherche par nom direct
        # -----------------------------------------------------------------
        if not partner and supplier_name and not self._is_placeholder_supplier_name(supplier_name):
            partner = Partner.search([("name", "ilike", supplier_name)], limit=1)

            if partner:
                _logger.info(
                    "[DocAI] Fournisseur trouvé par nom direct pour move %s : %s",
                    self.id,
                    partner.display_name,
                )

        # -----------------------------------------------------------------
        # 6) Rien trouvé
        # -----------------------------------------------------------------
        if not partner:
            _logger.warning(
                "[DocAI] Fournisseur non trouvé pour move %s | name=%s | vat=%s | registry=%s",
                self.id, supplier_name, supplier_vat, supplier_registry,
            )
            partner = self._get_unknown_supplier_partner()

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
    # PRÉPARATION DES VALEURS
    # -------------------------------------------------------------------------
    def _prepare_move_header_vals_from_docai(self, data):
        self.ensure_one()

        header_vals = self._get_docai_header_values(data)
        vals = {}

        partner = self._find_partner_from_docai_header(header_vals, data=data)
        currency = self._find_currency_from_docai_header(header_vals)

        if partner:
            vals["partner_id"] = partner.id

        if header_vals["invoice_number"]:
            vals["ref"] = header_vals["invoice_number"]

        if header_vals["invoice_date"]:
            vals["invoice_date"] = header_vals["invoice_date"]

        if header_vals["due_date"]:
            vals["invoice_date_due"] = header_vals["due_date"]

        if header_vals["payment_reference"]:
            vals["payment_reference"] = header_vals["payment_reference"]

        if currency:
            vals["currency_id"] = currency.id

        return vals, header_vals

    # -------------------------------------------------------------------------
    # TRAITEMENT COMPLET
    # -------------------------------------------------------------------------
    def action_docai_scan_json(self):
        """
        Met à jour l'en-tête puis appelle le traitement des line_items
        défini dans account_move_line.py.
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
            vals, header_vals = move._prepare_move_header_vals_from_docai(data)

            if vals:
                move.write(vals)
                _logger.info("[DocAI] En-tête mis à jour pour move %s : %s", move.id, vals)
            else:
                _logger.info("[DocAI] Aucun champ trouvé dans le JSON pour move %s", move.id)

            _logger.info(
                "[DocAI] Header lu pour move %s | supplier=%s | vat=%s | siret=%s | invoice=%s | date=%s | due=%s | currency=%s",
                move.id,
                header_vals.get("supplier_name"),
                header_vals.get("supplier_vat"),
                header_vals.get("supplier_siret"),
                header_vals.get("invoice_number"),
                header_vals.get("invoice_date"),
                header_vals.get("due_date"),
                header_vals.get("currency"),
            )

            try:
                move._docai_process_line_items(data)
            except AttributeError:
                _logger.warning(
                    "[DocAI] La méthode _docai_process_line_items n'existe pas encore pour move %s",
                    move.id,
                )
            except Exception as e:
                _logger.error(
                    "[DocAI] Erreur pendant le traitement des lignes pour move %s : %s",
                    move.id,
                    e,
                )
