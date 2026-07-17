# -*- coding: utf-8 -*-
# account_move_bank_receipt.py

import base64
import io
import json
import logging
import re
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMoveBankReceipt(models.Model):
    _inherit = "account.move"

    docai_cash_journal_id = fields.Many2one(
        "account.journal",
        string="Journal de caisse",
        domain="[('type', '=', 'cash'), ('company_id', '=', company_id)]",
        check_company=True,
        copy=False,
    )
    docai_bank_journal_id = fields.Many2one(
        "account.journal",
        string="Journal bancaire",
        domain="[('type', '=', 'bank'), ('company_id', '=', company_id)]",
        check_company=True,
        copy=False,
    )
    docai_transfer_account_id = fields.Many2one(
        "account.account",
        string="Compte de virements internes",
        domain="[('company_ids', 'in', company_id), ('reconcile', '=', True)]",
        check_company=True,
        copy=False,
        help="Compte 580 utilisé entre la pièce caisse et la pièce banque.",
    )
    docai_linked_move_id = fields.Many2one(
        "account.move",
        string="Pièce liée",
        readonly=True,
        copy=False,
    )
    docai_transfer_origin_id = fields.Many2one(
        "account.move",
        string="Pièce d'origine",
        readonly=True,
        copy=False,
    )
    docai_transfer_reference = fields.Char(
        string="Référence du transfert",
        readonly=True,
        copy=False,
        index=True,
    )
    docai_cash_transfer_done = fields.Boolean(
        string="Retrait / dépôt comptabilisé",
        readonly=True,
        copy=False,
    )

    # -------------------------------------------------------------------------
    # VALEURS PAR DEFAUT / ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("company_id")
    def _onchange_docai_cash_transfer_company(self):
        for move in self:
            if not move.company_id:
                continue
            move.docai_cash_journal_id = self.env["account.journal"].search([
                ("company_id", "=", move.company_id.id),
                ("type", "=", "cash"),
            ], limit=1)
            move.docai_bank_journal_id = self.env["account.journal"].search([
                ("company_id", "=", move.company_id.id),
                ("type", "=", "bank"),
            ], limit=1)
            move.docai_transfer_account_id = (
                move.company_id.transfer_account_id
                if hasattr(move.company_id, "transfer_account_id")
                else False
            )

    def _docai_prepare_cash_transfer_defaults(self):
        self.ensure_one()
        vals = {}
        if not self.docai_cash_journal_id:
            journal = self.env["account.journal"].search([
                ("company_id", "=", self.company_id.id),
                ("type", "=", "cash"),
            ], limit=1)
            if journal:
                vals["docai_cash_journal_id"] = journal.id
        if not self.docai_bank_journal_id:
            journal = self.env["account.journal"].search([
                ("company_id", "=", self.company_id.id),
                ("type", "=", "bank"),
            ], limit=1)
            if journal:
                vals["docai_bank_journal_id"] = journal.id
        if not self.docai_transfer_account_id:
            transfer_account = (
                self.company_id.transfer_account_id
                if hasattr(self.company_id, "transfer_account_id")
                else False
            )
            if transfer_account:
                vals["docai_transfer_account_id"] = transfer_account.id
        if vals:
            self.write(vals)

    # -------------------------------------------------------------------------
    # DETECTION ET EXTRACTION DU RECEPISSE BANCAIRE
    # -------------------------------------------------------------------------
    def _docai_is_bank_receipt(self, text):
        normalized = (text or "").upper()
        has_bank = (
            "CAISSE D'EPARGNE" in normalized
            or "CAISSE D’ÉPARGNE" in normalized
        )
        has_operation = any(token in normalized for token in (
            "MONTANT CREDITE",
            "MONTANT CRÉDITÉ",
            "MONTANT DEBITE",
            "MONTANT DÉBITÉ",
        ))
        return has_bank and has_operation

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
                return datetime.strptime(value.strip(), fmt).strftime("%d/%m/%Y")
            except ValueError:
                continue
        return value.strip()

    def _docai_extract_cash_breakdown(self, text):
        result = []
        pattern = re.compile(
            r"(\d+)\s+BILLET(?:\(S\)|S)?\s+DE\s+([\d.,]+)\s+EUROS?",
            re.IGNORECASE,
        )
        for quantity, unit_amount in pattern.findall(text or ""):
            unit_float = self._docai_bank_receipt_parse_amount(unit_amount)
            if unit_float is None:
                continue
            quantity_int = int(quantity)
            result.append({
                "quantity": quantity_int,
                "unit_amount": unit_float,
                "amount": round(quantity_int * unit_float, 2),
            })
        return result

    def _docai_extract_bank_receipt(self, text):
        upper = (text or "").upper()
        operation_type = None
        if "MONTANT CREDITE" in upper or "MONTANT CRÉDITÉ" in upper:
            operation_type = "cash_deposit"
        elif "MONTANT DEBITE" in upper or "MONTANT DÉBITÉ" in upper:
            operation_type = "cash_withdrawal"

        operation_date = self._docai_bank_receipt_match(
            r"\bDATE\s*[:\-]?\s*(\d{2}[/-]\d{2}[/-]\d{4})", text
        )
        operation_time = self._docai_bank_receipt_match(
            r"\bHEURE\s*[:\-]?\s*(\d{2}:\d{2}:\d{2})", text
        )
        atm_number = self._docai_bank_receipt_match(
            r"\bGAB\s*[:\-]?\s*(\d+)", text
        )
        operation_number = self._docai_bank_receipt_match(
            r"NUMERO\s+D['’]OPERATION\s*:\s*(\d+)", text
        )
        amount_text = self._docai_bank_receipt_match(
            r"MONTANT\s+(?:CREDITE|CRÉDITÉ|DEBITE|DÉBITÉ)"
            r"\s*:\s*([\d\s.,]+)\s*EUR",
            text,
        )
        amount = self._docai_bank_receipt_parse_amount(amount_text)
        account_number = self._docai_bank_receipt_match(
            r"SUR\s+LE\s+COMPTE\s*:\s*.*?(\d{6,})", text
        )
        card_last_digits = self._docai_bank_receipt_match(
            r"NUMERO\s+DE\s+CARTE\s*:\s*X+(\d{4})", text
        )
        bundle_count = self._docai_bank_receipt_match(
            r"NOMBRE\s+DE\s+LIASSE(?:\(S\)|S)?\s+DEPOSEE"
            r"(?:\(S\)|S)?\s*:\s*(\d+)",
            text,
        )

        return {
            "bank_name": "Caisse d'Épargne",
            "posting_mode": "internal_transfer",
            "operation_type": operation_type,
            "operation_date": self._docai_bank_receipt_parse_date(operation_date),
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
    # ENRICHISSEMENT SPECIALISE DU JSON SIMPLIFIE
    # -------------------------------------------------------------------------
    def _docai_enrich_formatted_json(self, parsed, formatted):
        formatted = super()._docai_enrich_formatted_json(parsed, formatted)
        text = parsed.get("text") or ""
        if not self._docai_is_bank_receipt(text):
            return formatted

        receipt = self._docai_extract_bank_receipt(text)
        result = dict(formatted)
        result["posting_mode"] = "internal_transfer"
        result["bank_receipt"] = receipt
        result["supplier_name"] = receipt["bank_name"]
        result["invoice_type"] = "bank_receipt"
        if receipt.get("operation_date"):
            result["invoice_date"] = receipt["operation_date"]
        if receipt.get("amount") is not None:
            result["total_amount"] = receipt["amount"]
        if receipt.get("currency"):
            result["currency"] = receipt["currency"]
        if receipt.get("operation_number"):
            result["supplier_payment_ref"] = receipt["operation_number"]
        return result

    def _docai_get_enriched_bank_receipt_data(self):
        """Retourne le JSON enrichi sans refaire un appel Google."""
        self.ensure_one()
        if not self.docai_json_raw:
            raise UserError(_("Aucun JSON complet DocAI n'est disponible."))
        try:
            parsed = json.loads(self.docai_json_raw)
        except Exception as exc:
            _logger.exception("[DocAI Banque] JSON complet invalide: %s", exc)
            raise UserError(_("Le JSON complet DocAI est invalide."))

        text = parsed.get("text") or ""
        if not self._docai_is_bank_receipt(text):
            raise UserError(_(
                "Le document n'est pas reconnu comme un récépissé bancaire "
                "Caisse d'Épargne."
            ))

        try:
            formatted = json.loads(self.docai_json) if self.docai_json else self._docai_empty_formatted_json()
        except Exception:
            formatted = self._docai_empty_formatted_json()
        formatted = self._docai_enrich_formatted_json(parsed, formatted)
        return formatted

    def action_docai_enrich_bank_receipt(self):
        self.ensure_one()
        formatted = self._docai_get_enriched_bank_receipt_data()
        self.write({
            "docai_json": json.dumps(formatted, indent=2, ensure_ascii=False),
            "docai_analyzed": True,
        })
        self._docai_prepare_cash_transfer_defaults()
        return {"type": "ir.actions.client", "tag": "reload"}

    # -------------------------------------------------------------------------
    # OUTILS COMPTABLES
    # -------------------------------------------------------------------------
    def _docai_parse_receipt_date(self, value):
        if not value:
            return fields.Date.context_today(self)
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return fields.Date.context_today(self)

    def _docai_get_journal_liquidity_account(self, journal):
        account = journal.default_account_id
        if not account:
            raise UserError(_(
                "Le journal %s ne possède pas de compte de liquidité par défaut."
            ) % journal.display_name)
        return account

    def _docai_validate_cash_transfer(self, receipt):
        self.ensure_one()
        if self.move_type != "entry":
            raise UserError(_(
                "Cette action est réservée aux écritures comptables diverses."
            ))
        if self.state != "draft":
            raise UserError(_("La pièce d'origine doit être en brouillon."))
        if self.docai_cash_transfer_done or self.docai_linked_move_id:
            raise UserError(_("Le transfert a déjà été créé pour cette pièce."))
        if self.line_ids.filtered(lambda line: not line.display_type):
            raise UserError(_(
                "La pièce contient déjà des lignes comptables. "
                "Supprimez-les avant de lancer l'opération."
            ))
        if not self.docai_cash_journal_id or not self.docai_bank_journal_id:
            raise UserError(_("Sélectionnez le journal de caisse et le journal bancaire."))
        if not self.docai_transfer_account_id:
            raise UserError(_("Sélectionnez le compte de virements internes (580)."))
        if self.docai_cash_journal_id.company_id != self.company_id or self.docai_bank_journal_id.company_id != self.company_id:
            raise UserError(_("Les deux journaux doivent appartenir à la société de la pièce."))
        if self.docai_cash_journal_id == self.docai_bank_journal_id:
            raise UserError(_("Le journal de caisse et le journal bancaire doivent être différents."))
        if receipt.get("operation_type") not in ("cash_deposit", "cash_withdrawal"):
            raise UserError(_("Le type d'opération dépôt/retrait est absent ou inconnu."))
        amount = receipt.get("amount")
        if not amount or amount <= 0:
            raise UserError(_("Le montant du récépissé est absent ou nul."))

    def _docai_build_common_reference(self, receipt, move_date):
        operation = receipt.get("operation_number") or "SANS-NUMERO"
        prefix = "DEPOT" if receipt.get("operation_type") == "cash_deposit" else "RETRAIT"
        return "DOC-AI-%s-%s-%s" % (
            prefix,
            move_date.strftime("%Y%m%d"),
            operation,
        )

    def _docai_line_commands(self, debit_account, credit_account, amount, label):
        return [
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

    # -------------------------------------------------------------------------
    # PDF : ORIGINAL IDENTIQUE + COPIE ANNOTEE
    # -------------------------------------------------------------------------
    def _docai_pdf_with_stamp(self, pdf_bytes, stamp_text):
        """Ajoute un cartouche sur la première page; retourne False si les libs manquent."""
        try:
            from pypdf import PdfReader, PdfWriter
            from reportlab.pdfgen import canvas
        except ImportError:
            _logger.warning(
                "[DocAI Banque] pypdf/reportlab absents: copie PDF non annotée uniquement."
            )
            return False

        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            if not reader.pages:
                return False
            first_page = reader.pages[0]
            width = float(first_page.mediabox.width)
            height = float(first_page.mediabox.height)

            overlay_buffer = io.BytesIO()
            c = canvas.Canvas(overlay_buffer, pagesize=(width, height))
            c.setFont("Helvetica-Bold", 12)
            c.drawRightString(width - 24, height - 28, stamp_text)
            c.setFont("Helvetica", 8)
            c.drawRightString(width - 24, height - 41, self.docai_transfer_reference or "")
            c.save()
            overlay_buffer.seek(0)
            overlay = PdfReader(overlay_buffer)
            first_page.merge_page(overlay.pages[0])

            writer = PdfWriter()
            writer.add_page(first_page)
            for page in reader.pages[1:]:
                writer.add_page(page)
            output = io.BytesIO()
            writer.write(output)
            return output.getvalue()
        except Exception as exc:
            _logger.exception("[DocAI Banque] Annotation PDF impossible: %s", exc)
            return False

    def _docai_copy_and_stamp_pdfs(self, linked_move, origin_stamp, linked_stamp):
        self.ensure_one()
        Attachment = self.env["ir.attachment"].sudo()
        originals = Attachment.search([
            ("res_model", "=", "account.move"),
            ("res_id", "=", self.id),
            ("mimetype", "=", "application/pdf"),
        ])
        for attachment in originals:
            # Copie binaire strictement identique sur la seconde pièce.
            attachment.copy({
                "name": attachment.name,
                "res_model": "account.move",
                "res_id": linked_move.id,
            })
            pdf_bytes = base64.b64decode(attachment.datas or b"")
            if not pdf_bytes:
                continue
            for move, stamp in ((self, origin_stamp), (linked_move, linked_stamp)):
                stamped = self._docai_pdf_with_stamp(pdf_bytes, stamp)
                if stamped:
                    base_name = re.sub(r"\.pdf$", "", attachment.name or "document", flags=re.I)
                    Attachment.create({
                        "name": "%s - %s.pdf" % (base_name, stamp),
                        "type": "binary",
                        "datas": base64.b64encode(stamped),
                        "mimetype": "application/pdf",
                        "res_model": "account.move",
                        "res_id": move.id,
                    })

    # -------------------------------------------------------------------------
    # BOUTON UNIQUE : RETRAIT / DEPOT D'ESPECES
    # -------------------------------------------------------------------------
    def action_docai_process_cash_transfer(self):
        self.ensure_one()
        self._docai_prepare_cash_transfer_defaults()

        data = self._docai_get_enriched_bank_receipt_data()
        receipt = data.get("bank_receipt") or {}
        self._docai_validate_cash_transfer(receipt)

        amount = float(receipt["amount"])
        move_date = self._docai_parse_receipt_date(receipt.get("operation_date"))
        operation_type = receipt["operation_type"]
        operation_number = receipt.get("operation_number") or ""
        common_ref = self._docai_build_common_reference(receipt, move_date)

        cash_account = self._docai_get_journal_liquidity_account(self.docai_cash_journal_id)
        bank_account = self._docai_get_journal_liquidity_account(self.docai_bank_journal_id)
        transfer_account = self.docai_transfer_account_id

        if operation_type == "cash_deposit":
            # Dépôt : la pièce d'origine est la sortie de caisse.
            origin_journal = self.docai_cash_journal_id
            linked_journal = self.docai_bank_journal_id
            origin_label = "Sortie caisse - dépôt d'espèces"
            linked_label = "Dépôt banque - espèces"
            origin_lines = self._docai_line_commands(
                transfer_account, cash_account, amount, origin_label
            )
            linked_lines = self._docai_line_commands(
                bank_account, transfer_account, amount, linked_label
            )
            origin_stamp = "SORTIE CAISSE"
            linked_stamp = "DÉPÔT BANQUE"
        else:
            # Retrait : la pièce d'origine est la sortie de banque.
            origin_journal = self.docai_bank_journal_id
            linked_journal = self.docai_cash_journal_id
            origin_label = "Retrait banque - espèces"
            linked_label = "Entrée caisse - retrait d'espèces"
            origin_lines = self._docai_line_commands(
                transfer_account, bank_account, amount, origin_label
            )
            linked_lines = self._docai_line_commands(
                cash_account, transfer_account, amount, linked_label
            )
            origin_stamp = "RETRAIT BANQUE"
            linked_stamp = "ENTRÉE CAISSE"

        if operation_number:
            origin_label += " - opération %s" % operation_number
            linked_label += " - opération %s" % operation_number
            # Recrée les commandes pour intégrer le libellé final.
            if operation_type == "cash_deposit":
                origin_lines = self._docai_line_commands(transfer_account, cash_account, amount, origin_label)
                linked_lines = self._docai_line_commands(bank_account, transfer_account, amount, linked_label)
            else:
                origin_lines = self._docai_line_commands(transfer_account, bank_account, amount, origin_label)
                linked_lines = self._docai_line_commands(cash_account, transfer_account, amount, linked_label)

        json_text = json.dumps(data, indent=2, ensure_ascii=False)
        self.write({
            "journal_id": origin_journal.id,
            "date": move_date,
            "ref": common_ref,
            "line_ids": origin_lines,
            "docai_json": json_text,
            "docai_transfer_reference": common_ref,
        })

        linked_move = self.create({
            "move_type": "entry",
            "company_id": self.company_id.id,
            "journal_id": linked_journal.id,
            "date": move_date,
            "ref": common_ref,
            "partner_id": self.partner_id.id or False,
            "line_ids": linked_lines,
            "docai_json_raw": self.docai_json_raw,
            "docai_json": json_text,
            "docai_analyzed": self.docai_analyzed,
            "docai_cash_journal_id": self.docai_cash_journal_id.id,
            "docai_bank_journal_id": self.docai_bank_journal_id.id,
            "docai_transfer_account_id": transfer_account.id,
            "docai_transfer_origin_id": self.id,
            "docai_transfer_reference": common_ref,
            "docai_cash_transfer_done": True,
        })

        self.write({
            "docai_linked_move_id": linked_move.id,
            "docai_cash_transfer_done": True,
        })
        linked_move.write({"docai_linked_move_id": self.id})

        self._docai_copy_and_stamp_pdfs(linked_move, origin_stamp, linked_stamp)

        return {
            "type": "ir.actions.act_window",
            "name": _("Pièce comptable liée"),
            "res_model": "account.move",
            "res_id": linked_move.id,
            "view_mode": "form",
            "target": "current",
        }

    # Compatibilité avec l'ancien bouton/méthode.
    def action_docai_create_bank_receipt_move_lines(self):
        return self.action_docai_process_cash_transfer()

    def action_docai_open_linked_move(self):
        self.ensure_one()
        linked = self.docai_linked_move_id or self.docai_transfer_origin_id
        if not linked:
            raise UserError(_("Aucune pièce liée n'est disponible."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Pièce comptable liée"),
            "res_model": "account.move",
            "res_id": linked.id,
            "view_mode": "form",
            "target": "current",
        }
