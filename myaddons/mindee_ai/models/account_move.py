# -*- coding: utf-8 -*-
# account_move.py (LabelStudio – JSON en base, OCR brut + JSON enrichi, suppression lignes, fournisseur obligatoire, logs debug)

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


class AccountMove(models.Model):
    _inherit = "account.move"

    ocr_raw_text = fields.Text("OCR Brut (Tesseract)", readonly=True, store=True)
    ocr_json_result = fields.Text("OCR JSON enrichi (LabelStudio)", readonly=True, store=True)
    mindee_local_response = fields.Text("Réponse OCR JSON (Tesseract)", readonly=True, store=True)

    # ------------------------------
    # Helpers
    # ------------------------------
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
            r"(?P<d>[0-9O]{1,2})\s*[\/-]\s*(?P<m>[0-9O]{1,2})\s*[\/-]\s*(?P<y>\d{2,4})",
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

        _logger.warning("[OCR][DATE] Parse KO: '%s' -> cleaned='%s'", date_str, cleaned)
        return None

    def _get_partner_labelstudio_json(self, partner):
        json_str = (partner.labelstudio_json or '').strip()
        if json_str:
            return json_str
        hist = self.env['mindee.labelstudio.history'].sudo().search(
            [('partner_id', '=', partner.id)], order='version_date desc, id desc', limit=1
        )
        if hist and (hist.json_content or '').strip():
            return hist.json_content
        return ''

    def _to_float(self, val):
        if not val:
            return 0.0
        try:
            return float(val.replace(",", ".").replace(" ", ""))
        except Exception:
            return 0.0

    def _find_tax(self, rate):
        if not rate or rate <= 0:
            return False
        return self.env["account.tax"].search([("amount", "=", rate)], limit=1)

    # ------------------------------
    # Action OCR
    # ------------------------------
    def action_ocr_fetch(self):
        venv_python = "/data/odoo/odoo18-venv/bin/python3"
        runner_path = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/models/invoice_labelmodel_runner.py"

        for move in self:
            if not move.partner_id:
                raise UserError("Vous devez d'abord renseigner un fournisseur avant de lancer l'OCR.")

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

                _logger.warning("[OCR][Runner] stdout=%s", result.stdout)
                _logger.warning("[OCR][Runner] stderr=%s", result.stderr)

                if not result.stdout.strip():
                    raise UserError("Runner n'a rien renvoyé, voir logs pour debug.")

                ocr_result = json.loads(result.stdout)
            except Exception as e:
                _logger.error("[OCR][Runner][EXCEPTION] %s", e)
                raise UserError(f"Erreur OCR avec LabelStudio runner : {e}")

            move.ocr_raw_text = ocr_result.get("ocr_raw", "")
            zones = ocr_result.get("ocr_zones", []) or []
            move.ocr_json_result = json.dumps(zones, indent=2, ensure_ascii=False)
            move.mindee_local_response = move.ocr_json_result

            # ---- Lecture zones ----
            def _pick_zone(labels):
                labels_norm = [self._strip_accents(l).lower() for l in labels]
                for z in zones:
                    lab = self._strip_accents((z.get('label') or '')).lower()
                    if any(lab.startswith(lbl) or lbl in lab for lbl in labels_norm):
                        return (z.get('text') or '').strip()
                return ''

            # Numéro facture
            inv_num = _pick_zone(['invoice number', 'numero facture', 'facture n', 'facture no', 'facture num'])
            if inv_num:
                move.ref = inv_num

            # Date facture
            inv_date = _pick_zone(['invoice date', 'date facture'])
            if inv_date:
                d = self._normalize_date(inv_date)
                if d:
                    move.invoice_date = d

            # Totaux
            total_ht = 0.0
            total_tva = 0.0
            total_ttc = 0.0
            for z in zones:
                label = (z.get("label") or "").lower()
                text = (z.get("text") or "").strip()
                clean_text = re.sub(r"[^\d,\.]", "", text)

                if "total brut ht" in label or "total net h.t" in label or "total ht" in label:
                    total_ht = self._to_float(clean_text)
                elif "total tva" in label or ("tva" in label and "total" in text.lower()):
                    total_tva = self._to_float(clean_text)
                elif "total ttc" in label or "net a payer" in label:
                    total_ttc = self._to_float(clean_text)

            _logger.warning("[OCR][TOTALS] HT=%s TVA=%s TTC=%s", total_ht, total_tva, total_ttc)

            # Efface anciennes lignes
            move.line_ids.unlink()

            # Ligne factice
            vat_rate = 0.0
            if total_ht > 0 and total_tva > 0:
                vat_rate = round((total_tva / total_ht) * 100, 2)
            tax = self._find_tax(vat_rate)

            move.line_ids.create({
                "move_id": move.id,
                "name": "Produit en attente (OCR)",
                "quantity": 1,
                "price_unit": total_ht if total_ht else 0.0,
                "account_id": move.journal_id.default_account_id.id,
                "tax_ids": [(6, 0, [tax.id])] if tax else False,
            })

            # Ligne note
            note_text = f"Totaux OCR : HT={total_ht} / TVA={total_tva} / TTC={total_ttc}"
            move.line_ids.create({# -*- coding: utf-8 -*-
# account_move.py (LabelStudio – JSON en base, OCR brut + JSON enrichi, suppression lignes, fournisseur obligatoire, logs debug)

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


class AccountMove(models.Model):
    _inherit = "account.move"

    ocr_raw_text = fields.Text("OCR Brut (Tesseract)", readonly=True, store=True)
    ocr_json_result = fields.Text("OCR JSON enrichi (LabelStudio)", readonly=True, store=True)
    mindee_local_response = fields.Text("Réponse OCR JSON (Tesseract)", readonly=True, store=True)

    # ------------------------------
    # Helpers
    # ------------------------------
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
            r"(?P<d>[0-9O]{1,2})\s*[\/-]\s*(?P<m>[0-9O]{1,2})\s*[\/-]\s*(?P<y>\d{2,4})",
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

        _logger.warning("[OCR][DATE] Parse KO: '%s' -> cleaned='%s'", date_str, cleaned)
        return None

    def _get_partner_labelstudio_json(self, partner):
        json_str = (partner.labelstudio_json or '').strip()
        if json_str:
            return json_str
        hist = self.env['mindee.labelstudio.history'].sudo().search(
            [('partner_id', '=', partner.id)], order='version_date desc, id desc', limit=1
        )
        if hist and (hist.json_content or '').strip():
            return hist.json_content
        return ''

    def _to_float(self, val):
        if not val:
            return 0.0
        try:
            return float(val.replace(",", ".").replace(" ", ""))
        except Exception:
            return 0.0

    def _find_tax(self, rate):
        if not rate or rate <= 0:
            return False
        return self.env["account.tax"].search([("amount", "=", rate)], limit=1)

    # ------------------------------
    # Action OCR
    # ------------------------------
    def action_ocr_fetch(self):
        venv_python = "/data/odoo/odoo18-venv/bin/python3"
        runner_path = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/models/invoice_labelmodel_runner.py"

        for move in self:
            if not move.partner_id:
                raise UserError("Vous devez d'abord renseigner un fournisseur avant de lancer l'OCR.")

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

                _logger.warning("[OCR][Runner] stdout=%s", result.stdout)
                _logger.warning("[OCR][Runner] stderr=%s", result.stderr)

                if not result.stdout.strip():
                    raise UserError("Runner n'a rien renvoyé, voir logs pour debug.")

                ocr_result = json.loads(result.stdout)
            except Exception as e:
                _logger.error("[OCR][Runner][EXCEPTION] %s", e)
                raise UserError(f"Erreur OCR avec LabelStudio runner : {e}")

            move.ocr_raw_text = ocr_result.get("ocr_raw", "")
            zones = ocr_result.get("ocr_zones", []) or []
            move.ocr_json_result = json.dumps(zones, indent=2, ensure_ascii=False)
            move.mindee_local_response = move.ocr_json_result

            # ---- Lecture zones ----
            def _pick_zone(labels):
                labels_norm = [self._strip_accents(l).lower() for l in labels]
                for z in zones:
                    lab = self._strip_accents((z.get('label') or '')).lower()
                    if any(lab.startswith(lbl) or lbl in lab for lbl in labels_norm):
                        return (z.get('text') or '').strip()
                return ''

            # Numéro facture
            inv_num = _pick_zone(['invoice number', 'numero facture', 'facture n', 'facture no', 'facture num'])
            if inv_num:
                move.ref = inv_num

            # Date facture
            inv_date = _pick_zone(['invoice date', 'date facture'])
            if inv_date:
                d = self._normalize_date(inv_date)
                if d:
                    move.invoice_date = d

            # Totaux
            total_ht = 0.0
            total_tva = 0.0
            total_ttc = 0.0
            for z in zones:
                label = (z.get("label") or "").lower()
                text = (z.get("text") or "").strip()
                clean_text = re.sub(r"[^\d,\.]", "", text)

                if "total brut ht" in label or "total net h.t" in label or "total ht" in label:
                    total_ht = self._to_float(clean_text)
                elif "total tva" in label or ("tva" in label and "total" in text.lower()):
                    total_tva = self._to_float(clean_text)
                elif "total ttc" in label or "net a payer" in label:
                    total_ttc = self._to_float(clean_text)

            _logger.warning("[OCR][TOTALS] HT=%s TVA=%s TTC=%s", total_ht, total_tva, total_ttc)

            # Efface anciennes lignes
            move.line_ids.unlink()

            # Ligne factice
            vat_rate = 0.0
            if total_ht > 0 and total_tva > 0:
                vat_rate = round((total_tva / total_ht) * 100, 2)
            tax = self._find_tax(vat_rate)

            move.line_ids.create({
                "move_id": move.id,
                "name": "Produit en attente (OCR)",
                "quantity": 1,
                "price_unit": total_ht if total_ht else 0.0,
                "account_id": move.journal_id.default_account_id.id,
                "tax_ids": [(6, 0, [tax.id])] if tax else False,
            })

            # Ligne note
            note_text = f"Totaux OCR : HT={total_ht} / TVA={total_tva} / TTC={total_ttc}"
            move.line_ids.create({
                "move_id": move.id,
                "name": note_text,
                "display_type": "line_note",
            })

        return True

                "move_id": move.id,
                "name": note_text,
                "display_type": "line_note",
            })

        return True
