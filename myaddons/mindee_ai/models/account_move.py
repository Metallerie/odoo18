# -*- coding: utf-8 -*-
# account_move.py (LabelStudio – OCR avec logs chatter + Python,
# suppression lignes produits, extraction lignes + commentaires)

import base64
import json
import logging
import re
import subprocess
import tempfile
import unicodedata
from datetime import date

from odoo import models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MONTHS_FR_MAP = {
    "janvier": "01", "janv": "01", "jan": "01",
    "fevrier": "02", "fevr": "02", "fev": "02",
    "mars": "03",
    "avril": "04", "avr": "04",
    "mai": "05",
    "juin": "06",
    "juillet": "07", "juil": "07",
    "aout": "08",
    "septembre": "09", "sept": "09",
    "octobre": "10", "oct": "10",
    "novembre": "11", "nov": "11",
    "decembre": "12", "dec": "12",
}

IGNORE_VALUES = {
    "réf.", "ref", "designation", "désignation",
    "qté", "unité", "prix unitaire", "montant", "tva"
}


class AccountMove(models.Model):
    _inherit = "account.move"

    ocr_raw_text = fields.Text(
        string="OCR Brut (Tesseract)",
        readonly=True,
        store=True,
    )
    ocr_json_result = fields.Text(
        string="OCR JSON enrichi (LabelStudio)",
        readonly=True,
        store=True,
    )
    mindee_local_response = fields.Text(
        string="Réponse OCR JSON (Tesseract)",
        readonly=True,
        store=True,
    )

    # === Helpers ===
    def _log(self, move, level, msg, *args):
        """Log Python + chatter Odoo (debug visible dans facture)."""
        text = msg % args if args else msg
        try:
            getattr(_logger, level)(text)
        except Exception:
            _logger.warning(text)
        try:
            move.message_post(body=f"[OCR] {text}")
        except Exception:
            pass

    def _strip_accents(self, s):
        if not s:
            return s
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")

    def _norm(self, s):
        return " ".join(self._strip_accents((s or "")).lower().split())

    def _preclean_text(self, s):
        if not s:
            return s
        s = " ".join(str(s).split())
        s = re.sub(r"\bO(?=\d)", "0", s)
        s = re.sub(r"(?<=\d)[Il](?=\d)", "1", s)
        s = s.replace("-", "/").replace(".", "/")
        return s

    def _normalize_date(self, date_str):
        if not date_str:
            return None
        raw = str(date_str).strip()
        cleaned = self._preclean_text(raw)
        cleaned_lc = cleaned.lower()
        cleaned_lc_noacc = self._strip_accents(cleaned_lc)

        m = re.search(
            r"(?P<d>[0-9O]{1,2})[\/-](?P<m>[0-9O]{1,2})[\/-](?P<y>\d{2,4})",
            cleaned_lc_noacc,
        )
        if m:
            try:
                dd = int(m.group("d").replace("O", "0"))
                mm = int(m.group("m").replace("O", "0"))
                yy = int(m.group("y"))
                if yy < 100:
                    yy = 2000 + yy if yy <= 69 else 1900 + yy
                return date(yy, mm, dd)
            except Exception:
                pass

        m2 = re.search(
            r"(?P<d>[0-9O]{1,2})\s+(?P<mon>[a-zA-Z\u00C0-\u017F\.]+)\s+(?P<y>\d{2,4})",
            cleaned_lc,
        )
        if m2:
            try:
                dd = int(m2.group("d").replace("O", "0"))
                mon_key = self._strip_accents(m2.group("mon").replace(".", "").lower())
                yy = int(m2.group("y"))
                if yy < 100:
                    yy = 2000 + yy if yy <= 69 else 1900 + yy
                mm = MONTHS_FR_MAP.get(mon_key)
                if mm:
                    return date(yy, int(mm), dd)
            except Exception:
                pass

        self._log(self, "warning", "DATE Parse KO: '%s' -> cleaned='%s'", date_str, cleaned)
        return None

    def _get_partner_labelstudio_json(self, partner):
        json_str = (partner.labelstudio_json or "").strip()
        if json_str:
            return json_str
        hist = self.env["mindee.labelstudio.history"].sudo().search(
            [("partner_id", "=", partner.id)], order="version_date desc, id desc", limit=1
        )
        if hist and (hist.json_content or "").strip():
            return hist.json_content
        return ""

    def _to_float(self, val):
        if not val or val == "NUL":
            return 0.0
        val = val.replace(" ", "").replace(",", ".")
        try:
            return float(val)
        except Exception:
            return 0.0

    def _find_tax(self, vat_rate):
        if vat_rate <= 0:
            return False
        tax = self.env["account.tax"].search(
            [("amount", "=", vat_rate), ("type_tax_use", "=", "purchase")], limit=1
        )
        return tax or False

    # === Action principale ===
    def action_ocr_fetch(self):
        venv_python = "/data/odoo/odoo18-venv/bin/python3"
        runner_path = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/models/invoice_labelmodel_runner.py"

        for move in self:
            if not move.partner_id:
                raise UserError("Vous devez d'abord renseigner un fournisseur avant de lancer l'OCR.")

            self._log(move, "warning", "=== START OCR fetch (move=%s id=%s) ===", move.name or "", move.id)

            model_json = self._get_partner_labelstudio_json(move.partner_id)
            if not model_json:
                raise UserError(f"Aucun modèle JSON trouvé pour le fournisseur {move.partner_id.display_name}.")

            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = pdf_attachments[0]

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                pdf_path = tmp_pdf.name
                tmp_pdf.write(base64.b64decode(attachment.datas))

            with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8", suffix=".json") as tmp_js:
                json_path = tmp_js.name
                tmp_js.write(model_json)

            try:
                result = subprocess.run(
                    [venv_python, runner_path, pdf_path, json_path],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=180, check=True, encoding="utf-8",
                )
                if not result.stdout.strip():
                    raise UserError("Runner n'a rien renvoyé, voir logs pour debug.")

                ocr_result = json.loads(result.stdout)
            except Exception as e:
                self._log(move, "error", "Runner Exception: %s", e)
                raise UserError(f"Erreur OCR runner : {e}")

            move.ocr_raw_text = ocr_result.get("ocr_raw", "")
            zones = ocr_result.get("ocr_zones", []) or []
            move.ocr_json_result = json.dumps(zones, indent=2, ensure_ascii=False)
            move.mindee_local_response = move.ocr_json_result

            # Supprime les anciennes lignes produits
            old_lines = move.line_ids.filtered(lambda l: l.display_type in (False, "product"))
            count_removed = len(old_lines)
            old_lines.unlink()
            self._log(move, "warning", "%s anciennes lignes PRODUITS supprimées", count_removed)

            # Extraction lignes
            rows = {}
            tolerance = 0.5
            for z in zones:
                if z.get("label") in ["Reference", "Description", "Quantity", "Unité", "Unit Price", "Amount HT", "VAT"]:
                    text = (z.get("text") or "").strip()
                    if self._norm(text) in IGNORE_VALUES:
                        continue
                    y = round(float(z.get("y", 0)) / tolerance) * tolerance
                    if y not in rows:
                        rows[y] = {}
                    rows[y][z.get("label")] = text

            product_lines, comment_lines = [], []
            default_tax = self.env["account.tax"].search([("type_tax_use", "=", "purchase")], limit=1)

            if not rows:
                self._log(move, "warning", "Aucune ligne détectée")

            for y, data in sorted(rows.items()):
                ref = data.get("Reference", "")
                desc = data.get("Description", "")
                qty_raw = data.get("Quantity", "")
                pu_raw = data.get("Unit Price", "")
                amt_raw = data.get("Amount HT", "")
                uom = data.get("Unité", "")

                qty = self._to_float(qty_raw)
                price_unit = self._to_float(pu_raw)
                amount = self._to_float(amt_raw)

                vat_text = data.get("VAT", "")
                vat_rate = self._to_float(vat_text)
                tax = self._find_tax(vat_rate) or default_tax

                self._log(move, "warning",
                          "ROW y=%s | Ref=%s | Desc=%s | Qté=%s | U=%s | PU=%s | Montant=%s | TVA=%s",
                          y, ref, desc, qty_raw, uom, pu_raw, amt_raw, vat_rate)

                if qty > 0 and price_unit > 0:
                    product_lines.append({
                        "name": f"[{ref}] {desc}" if ref else desc or "Ligne sans désignation",
                        "quantity": qty,
                        "price_unit": price_unit,
                        "account_id": move.journal_id.default_account_id.id,
                        "tax_ids": [(6, 0, [tax.id])] if tax else False,
                    })
                else:
                    comment_lines.append(
                        f"Ligne OCR incomplète : Ref={ref}, Desc={desc}, Qté={qty_raw}, U={uom}, PU={pu_raw}, Montant={amt_raw}"
                    )

            for line in product_lines:
                move.line_ids.create({"move_id": move.id, **line})

            for comment in comment_lines:
                move.line_ids.create({"move_id": move.id, "name": comment, "display_type": "line_note"})

            self._log(move, "info", "%s lignes produit et %s commentaires ajoutés", len(product_lines), len(comment_lines))
            self._log(move, "warning", "=== END OCR fetch (move=%s id=%s) ===", move.name or "", move.id)

        return True
