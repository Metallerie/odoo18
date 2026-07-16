# -*- coding: utf-8 -*-
# account_move_bank_receipt.py

import json
import logging
import re
from datetime import datetime

from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMoveBankReceipt(models.Model):
    _inherit = "account.move"

    # -------------------------------------------------------------------------
    # DETECTION
    # -------------------------------------------------------------------------
    def _docai_is_bank_receipt(self, text):
        """
        Détecte un récépissé bancaire de dépôt ou retrait d'espèces.

        La détection reste volontairement stricte afin de ne pas modifier
        les tickets de caisse classiques traités par l'Expense Parser.
        """
        normalized = (text or "").upper()

        has_bank = (
            "CAISSE D'EPARGNE" in normalized
            or "CAISSE D’ÉPARGNE" in normalized
        )
        has_operation = (
            "MONTANT CREDITE" in normalized
            or "MONTANT CRÉDITÉ" in normalized
            or "MONTANT DEBITE" in normalized
            or "MONTANT DÉBITÉ" in normalized
        )

        return has_bank and has_operation

    # -------------------------------------------------------------------------
    # OUTILS D'EXTRACTION
    # -------------------------------------------------------------------------
    def _docai_bank_receipt_match(self, pattern, text, flags=re.IGNORECASE):
        match = re.search(pattern, text or "", flags)
        return match.group(1).strip() if match else None

    def _docai_bank_receipt_parse_amount(self, value):
        if value in (None, ""):
            return None

        cleaned = str(value).strip().replace(" ", "").replace(",", ".")

        try:
            return float(cleaned)
        except (TypeError, ValueError):
            return None

    def _docai_bank_receipt_parse_date(self, value):
        if not value:
            return None

        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value.strip(), fmt).strftime(
                    "%d/%m/%Y"
                )
            except ValueError:
                continue

        return value.strip()

    def _docai_extract_cash_breakdown(self, text):
        """
        Extrait les lignes du type :
        2 BILLET(S) DE 20 EUROS
        4 BILLET(S) DE 50 EUROS
        """
        result = []

        pattern = re.compile(
            r"(\d+)\s+BILLET(?:\(S\)|S)?\s+DE\s+([\d.,]+)\s+EUROS?",
            re.IGNORECASE,
        )

        for quantity, unit_amount in pattern.findall(text or ""):
            quantity_int = int(quantity)
            unit_float = self._docai_bank_receipt_parse_amount(unit_amount)

            if unit_float is None:
                continue

            result.append({
                "quantity": quantity_int,
                "unit_amount": unit_float,
                "amount": round(quantity_int * unit_float, 2),
            })

        return result

    def _docai_extract_bank_receipt(self, text):
        upper = (text or "").upper()

        operation_type = None
        if (
            "MONTANT CREDITE" in upper
            or "MONTANT CRÉDITÉ" in upper
        ):
            operation_type = "cash_deposit"
        elif (
            "MONTANT DEBITE" in upper
            or "MONTANT DÉBITÉ" in upper
        ):
            operation_type = "cash_withdrawal"

        operation_date = self._docai_bank_receipt_match(
            r"\bDATE\s*[:\-]?\s*(\d{2}[/-]\d{2}[/-]\d{4})",
            text,
        )
        operation_time = self._docai_bank_receipt_match(
            r"\bHEURE\s*[:\-]?\s*(\d{2}:\d{2}:\d{2})",
            text,
        )
        atm_number = self._docai_bank_receipt_match(
            r"\bGAB\s*[:\-]?\s*(\d+)",
            text,
        )
        operation_number = self._docai_bank_receipt_match(
            r"NUMERO\s+D['’]OPERATION\s*:\s*(\d+)",
            text,
        )

        amount_text = self._docai_bank_receipt_match(
            r"MONTANT\s+(?:CREDITE|CRÉDITÉ|DEBITE|DÉBITÉ)"
            r"\s*:\s*([\d\s.,]+)\s*EUR",
            text,
        )
        amount = self._docai_bank_receipt_parse_amount(amount_text)

        account_number = self._docai_bank_receipt_match(
            r"SUR\s+LE\s+COMPTE\s*:\s*.*?(\d{6,})",
            text,
        )
        card_last_digits = self._docai_bank_receipt_match(
            r"NUMERO\s+DE\s+CARTE\s*:\s*X+(\d{4})",
            text,
        )
        bundle_count = self._docai_bank_receipt_match(
            r"NOMBRE\s+DE\s+LIASSE(?:\(S\)|S)?\s+DEPOSEE"
            r"(?:\(S\)|S)?\s*:\s*(\d+)",
            text,
        )

        return {
            "bank_name": "Caisse d'Épargne",
            "operation_type": operation_type,
            "operation_date": self._docai_bank_receipt_parse_date(
                operation_date
            ),
            "operation_time": operation_time,
            "atm_number": atm_number,
            "operation_number": operation_number,
            "amount": amount,
            "currency": "EUR" if amount is not None else None,
            "account_number": account_number,
            "card_last_digits": card_last_digits,
            "bundle_count": int(bundle_count) if bundle_count else None,
            "cash_breakdown": self._docai_extract_cash_breakdown(text),
        }

    # -------------------------------------------------------------------------
    # ENRICHISSEMENT DU JSON SIMPLIFIE
    # -------------------------------------------------------------------------
    def _docai_enrich_formatted_json(self, parsed, formatted):
        formatted = super()._docai_enrich_formatted_json(
            parsed,
            formatted,
        )

        text = parsed.get("text") or ""

        if not self._docai_is_bank_receipt(text):
            return formatted

        receipt = self._docai_extract_bank_receipt(text)

        result = dict(formatted)
        result["bank_receipt"] = receipt

        # Correction des champs communs mal reconnus par l'Expense Parser.
        result["supplier_name"] = receipt["bank_name"]
        result["invoice_type"] = "bank_receipt"

        if receipt.get("operation_date"):
            result["invoice_date"] = receipt["operation_date"]

        if receipt.get("amount") is not None:
            result["total_amount"] = receipt["amount"]

        if receipt.get("currency"):
            result["currency"] = receipt["currency"]

        if receipt.get("operation_number"):
            result["supplier_payment_ref"] = receipt[
                "operation_number"
            ]

        _logger.info(
            "[DocAI Banque] JSON enrichi pour move %s",
            self.id or "non enregistré",
        )

        return result

    # -------------------------------------------------------------------------
    # BOUTON : RECONSTRUIRE LE JSON BANCAIRE DEPUIS LE JSON COMPLET EXISTANT
    # -------------------------------------------------------------------------
    def action_docai_enrich_bank_receipt(self):
        """
        Utilise le JSON complet déjà stocké dans docai_json_raw.
        Aucun nouvel appel à Google n'est effectué.
        """
        self.ensure_one()

        if not self.docai_json_raw:
            raise UserError(
                _("Aucun JSON complet DocAI n'est disponible.")
            )

        try:
            parsed = json.loads(self.docai_json_raw)
        except Exception as e:
            _logger.exception(
                "[DocAI Banque] JSON complet invalide : %s",
                e,
            )
            raise UserError(_("Le JSON complet DocAI est invalide."))

        text = parsed.get("text") or ""
        if not self._docai_is_bank_receipt(text):
            raise UserError(
                _(
                    "Le document n'est pas reconnu comme un récépissé "
                    "bancaire Caisse d'Épargne."
                )
            )

        if self.docai_json:
            try:
                formatted = json.loads(self.docai_json)
            except Exception:
                formatted = self._docai_empty_formatted_json()
        else:
            formatted = self._docai_empty_formatted_json()

        formatted = self._docai_enrich_formatted_json(
            parsed,
            formatted,
        )

        self.write({
            "docai_json": json.dumps(
                formatted,
                indent=2,
                ensure_ascii=False,
            ),
            "docai_analyzed": True,
        })

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    # -------------------------------------------------------------------------
    # CREATION DE L'ECRITURE COMPTABLE
    # -------------------------------------------------------------------------
    def _docai_get_bank_receipt_accounts(self):
        """
        Les codes sont configurables dans Paramètres techniques :
          docai_ai.bank_account_code
          docai_ai.cash_account_code

        Valeurs par défaut :
          banque : 512000
          caisse : 531000
        """
        self.ensure_one()

        ICP = self.env["ir.config_parameter"].sudo()
        bank_code = ICP.get_param(
            "docai_ai.bank_account_code",
            "512001",
        )
        cash_code = ICP.get_param(
            "docai_ai.cash_account_code",
            "531000",
        )

        Account = self.env["account.account"].sudo()

        bank_account = Account.search([
            ("code", "=", bank_code),
            ("company_ids", "in", self.company_id.id),
        ], limit=1)

        cash_account = Account.search([
            ("code", "=", cash_code),
            ("company_ids", "in", self.company_id.id),
        ], limit=1)

        if not bank_account:
            raise UserError(
                _(
                    "Compte bancaire introuvable : %s.\n"
                    "Configure docai_ai.bank_account_code."
                )
                % bank_code
            )

        if not cash_account:
            raise UserError(
                _(
                    "Compte caisse introuvable : %s.\n"
                    "Configure docai_ai.cash_account_code."
                )
                % cash_code
            )

        return bank_account, cash_account

    def action_docai_create_bank_receipt_move_lines(self):
        """
        Crée les deux lignes sur la pièce comptable brouillon existante.

        Sécurité :
        - uniquement move_type = entry ;
        - uniquement brouillon ;
        - refuse si des lignes non automatiques existent déjà.
        """
        self.ensure_one()

        if self.move_type != "entry":
            raise UserError(
                _(
                    "Cette action est réservée aux pièces comptables "
                    "de type Écriture comptable."
                )
            )

        if self.state != "draft":
            raise UserError(
                _("La pièce comptable doit être en brouillon.")
            )

        if not self.docai_json:
            raise UserError(
                _("Le JSON simplifié DocAI est absent.")
            )

        try:
            data = json.loads(self.docai_json)
        except Exception:
            raise UserError(_("Le JSON simplifié DocAI est invalide."))

        receipt = data.get("bank_receipt") or {}
        if not receipt:
            raise UserError(
                _(
                    "Le JSON ne contient pas de section "
                    "'bank_receipt'."
                )
            )

        amount = receipt.get("amount")
        operation_type = receipt.get("operation_type")

        if amount in (None, 0, 0.0):
            raise UserError(
                _("Le montant bancaire est absent ou nul.")
            )

        if operation_type not in (
            "cash_deposit",
            "cash_withdrawal",
        ):
            raise UserError(
                _("Le type d'opération bancaire est inconnu.")
            )

        existing_lines = self.line_ids.filtered(
            lambda line: not line.display_type
        )
        if existing_lines:
            raise UserError(
                _(
                    "La pièce contient déjà des lignes comptables. "
                    "Supprime-les avant de lancer cette action."
                )
            )

        bank_account, cash_account = (
            self._docai_get_bank_receipt_accounts()
        )

        operation_number = (
            receipt.get("operation_number")
            or ""
        )
        operation_date = (
            receipt.get("operation_date")
            or ""
        )

        if operation_type == "cash_deposit":
            label = "Dépôt espèces Caisse d'Épargne"
            debit_account = bank_account
            credit_account = cash_account
        else:
            label = "Retrait espèces Caisse d'Épargne"
            debit_account = cash_account
            credit_account = bank_account

        if operation_number:
            label += f" - opération {operation_number}"

        line_commands = [
            (0, 0, {
                "name": label,
                "account_id": debit_account.id,
                "debit": amount,
                "credit": 0.0,
            }),
            (0, 0, {
                "name": label,
                "account_id": credit_account.id,
                "debit": 0.0,
                "credit": amount,
            }),
        ]

        vals = {
            "line_ids": line_commands,
            "ref": label,
        }

        parsed_date = None
        if operation_date:
            try:
                parsed_date = datetime.strptime(
                    operation_date,
                    "%d/%m/%Y",
                ).date()
            except ValueError:
                parsed_date = None

        if parsed_date:
            vals["date"] = parsed_date

        self.write(vals)

        _logger.info(
            "[DocAI Banque] Écriture créée sur move %s : %s",
            self.id,
            label,
        )

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }
