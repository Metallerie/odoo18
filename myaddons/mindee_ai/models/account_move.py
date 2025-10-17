# -*- coding: utf-8 -*-
# account_move.py (OCR Mindee – création ligne factice si pas de lignes)

import base64
import json
import logging
import re
import unicodedata
from datetime import date

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    ocr_json = fields.Text("OCR JSON brut")
    ocr_debug = fields.Text("OCR Debug Infos")

    # -----------------------------
    # Conversion sécurisée float
    # -----------------------------
    def _to_float(self, txt):
        if not txt:
            return 0.0
        txt = txt.replace(" ", "").replace(",", ".")
        try:
            return float(txt)
        except Exception:
            return 0.0

    # -----------------------------
    # Recherche taxe
    # -----------------------------
    def _find_tax(self, vat_rate):
        tax = self.env["account.tax"].search(
            [("amount", "=", vat_rate), ("type_tax_use", "=", "purchase")], limit=1
        )
        if not tax and vat_rate != 0:
            tax = self.env["account.tax"].create(
                {
                    "name": f"TVA {vat_rate}%",
                    "amount": vat_rate,
                    "type_tax_use": "purchase",
                }
            )
        return tax

    # -----------------------------
    # Remplir depuis OCR
    # -----------------------------
    def action_fill_from_ocr(self):
        for move in self:
            if not move.ocr_json:
                raise UserError("Aucun JSON OCR disponible.")

            try:
                zones = json.loads(move.ocr_json)
            except Exception as e:
                raise UserError(f"Erreur lecture JSON OCR : {e}")

            total_ht = 0.0
            total_tva = 0.0
            total_ttc = 0.0

            # --------------------------
            # Analyse zones OCR
            # --------------------------
            for z in zones:
                label = (z.get("label") or "").lower().strip()
                text = (z.get("text") or "").strip()
                _logger.warning("[OCR][ZONE] label=%s text=%s", label, text)

                # Nettoyage du texte
                clean_text = re.sub(r"[^\d,\.]", "", text)

                if "total brut ht" in label or "total net h.t" in label or "total ht" in label:
                    total_ht = self._to_float(clean_text)
                elif "total tva" in label or (label == "tva" and "total" in text.lower()):
                    total_tva = self._to_float(clean_text)
                elif "total ttc" in label or "net a payer" in label:
                    total_ttc = self._to_float(clean_text)

            _logger.warning("[OCR][TOTALS DETECTED] HT=%s | TVA=%s | TTC=%s", total_ht, total_tva, total_ttc)

            # --------------------------
            # Suppression anciennes lignes
            # --------------------------
            move.line_ids.unlink()

            # --------------------------
            # Ligne factice produit
            # --------------------------
            vat_rate = 0.0
            if total_ht > 0 and total_tva > 0:
                vat_rate = round((total_tva / total_ht) * 100, 2)
            tax = self._find_tax(vat_rate)

            move.line_ids.create({
                "move_id": move.id,
                "name": "Produit en attente (OCR)",
                "quantity": 1,
                "price_unit": total_ht if total_ht > 0 else 0.0,
                "account_id": move.journal_id.default_account_id.id,
                "tax_ids": [(6, 0, [tax.id])] if tax else False,
            })

            # --------------------------
            # Ligne note informative
            # --------------------------
            note_text = f"Totaux OCR détectés : HT={total_ht} / TVA={total_tva} / TTC={total_ttc}"
            move.line_ids.create({
                "move_id": move.id,
                "name": note_text,
                "display_type": "line_note",
            })

            move.ocr_debug = json.dumps(
                {"total_ht": total_ht, "total_tva": total_tva, "total_ttc": total_ttc}, indent=2
            )
            _logger.warning("[OCR][FINAL DEBUG] %s", move.ocr_debug)
