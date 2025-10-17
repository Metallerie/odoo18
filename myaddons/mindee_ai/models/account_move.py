# -*- coding: utf-8 -*-
# account_move.py (OCR → LabelStudio, Totaux HT/TVA/TTC → ligne produit FACTURE EN ATTENTE)

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
    "mars": "03", "avril": "04", "avr": "04",
    "mai": "05", "juin": "06",
    "juillet": "07", "juil": "07",
    "aout": "08",
    "septembre": "09", "sept": "09",
    "octobre": "10", "oct": "10",
    "novembre": "11", "nov": "11",
    "decembre": "12", "dec": "12",
}

class AccountMove(models.Model):
    _inherit = "account.move"

    ocr_raw_text = fields.Text(string="OCR Brut (Tesseract)", readonly=True, store=True)
    ocr_json_result = fields.Text(string="OCR JSON enrichi (LabelStudio)", readonly=True, store=True)
    mindee_local_response = fields.Text(string="Réponse OCR JSON (Tesseract)", readonly=True, store=True)

    # ------------------------------
    # Utils
    # ------------------------------
    def _strip_accents(self, s):
        if not s:
            return s
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")

    def _preclean_text(self, s):
        if not s:
            return s
        s = " ".join(str(s).split())
        s = re.sub(r"\bO(?=\d)", "0", s)
        s = re.sub(r"(?<=\d)[Il](?=\d)", "1", s)
        return s

    def _normalize_date(self, date_str):
        if not date_str:
            return None
        raw = str(date_str).strip()
        cleaned = self._preclean_text(raw).lower()
        cleaned_noacc = self._strip_accents(cleaned)

        m = re.search(r"(?P<d>\d{1,2})[\/\-\s](?P<m>\d{1,2})[\/\-\s](?P<y>\d{2,4})", cleaned_noacc)
        if m:
            try:
                dd, mm, yy = int(m.group("d")), int(m.group("m")), int(m.group("y"))
                if yy < 100:
                    yy = 2000 + yy if yy <= 69 else 1900 + yy
                return date(yy, mm, dd)
            except Exception:
                return None

        m2 = re.search(r"(?P<d>\d{1,2})\s+(?P<mon>[a-zA-Z\u00C0-\u017F\.]+)\s+(?P<y>\d{2,4})", cleaned)
        if m2:
            try:
                dd, yy = int(m2.group("d")), int(m2.group("y"))
                mon_key = self._strip_accents(m2.group("mon").replace(".", "").lower())
                if yy < 100:
                    yy = 2000 + yy if yy <= 69 else 1900 + yy
                mm = MONTHS_FR_MAP.get(mon_key)
                if mm:
                    return date(yy, int(mm), dd)
            except Exception:
                return None

        _logger.warning("[OCR][DATE] Parse KO: %s", date_str)
        return None

    def _to_float(self, val):
        """Convertit un texte OCR en float robuste"""
        if not val or val == "NUL":
            return 0.0
        val = str(val).strip()
        m = re.findall(r"\d[\d\s.,]*", val)
        if m:
            val = m[-1]  # on garde le dernier nombre trouvé
        val = val.replace(" ", "").replace(",", ".")
        try:
            return float(val)
        except Exception:
            return 0.0

    def _get_partner_labelstudio_json(self, partner):
        json_str = (partner.labelstudio_json or '').strip()
        if json_str:
            return json_str
        hist = self.env['mindee.labelstudio.history'].sudo().search(
            [('partner_id', '=', partner.id)], order='version_date desc, id desc', limit=1
        )
        return (hist.json_content or '').strip() if hist else ''

    # ------------------------------
    # Action principale
    # ------------------------------
    def action_ocr_fetch(self):
        venv_python = "/data/odoo/odoo18-venv/bin/python3"
        runner_path = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/models/invoice_labelmodel_runner.py"

        for move in self:
            if not move.partner_id:
                raise UserError("⚠️ Fournisseur obligatoire avant OCR.")

            model_json = self._get_partner_labelstudio_json(move.partner_id)
            if not model_json:
                raise UserError(f"⚠️ Aucun modèle JSON pour {move.partner_id.display_name}.")

            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("⚠️ Pas de pièce jointe PDF trouvée.")
            attachment = pdf_attachments[0]

            # Temp files
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                tmp_pdf.write(base64.b64decode(attachment.datas))
                pdf_path = tmp_pdf.name
            with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8", suffix=".json") as tmp_js:
                tmp_js.write(model_json)
                json_path = tmp_js.name

            try:
                result = subprocess.run(
                    [venv_python, runner_path, pdf_path, json_path],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=180, check=True, encoding="utf-8",
                )
                if not result.stdout.strip():
                    raise UserError("⚠️ Runner n'a rien renvoyé (stdout vide).")
                ocr_result = json.loads(result.stdout)
            except Exception as e:
                raise UserError(f"❌ Erreur OCR runner : {e}")

            # Sauvegarde brute
            move.ocr_raw_text = ocr_result.get("ocr_raw", "")
            zones = ocr_result.get("ocr_zones", []) or []
            move.ocr_json_result = json.dumps(zones, indent=2, ensure_ascii=False)
            move.mindee_local_response = move.ocr_json_result

            # Helper zone picker
            def _pick_zone(labels):
                labels_norm = [self._strip_accents(l).lower() for l in labels]
                for z in zones:
                    lab = self._strip_accents((z.get("label") or "")).lower()
                    if any(lab.startswith(lbl) or lbl in lab for lbl in labels_norm):
                        return (z.get("text") or "").strip()
                return ""

            # --- Référence facture ---
            inv_num = _pick_zone(["invoice number", "facture n", "facture no", "facture num"])
            if inv_num:
                move.ref = re.sub(r"(?i)facture\s*(n°|no|num|number)?[:\-]?", "", inv_num).strip()

            # --- Date facture ---
            inv_date = _pick_zone(["invoice date", "date facture", "date de facture"])
            if inv_date:
                d = self._normalize_date(inv_date)
                if d:
                    move.invoice_date = d

            # --- Totaux ---
            total_ht = self._to_float(_pick_zone(["total ht", "total brut ht", "total net ht", "total net h.t"]))
            total_tva = self._to_float(_pick_zone(["total tva", "tva"]))
            total_ttc = self._to_float(_pick_zone(["total ttc", "net a payer"]))

            _logger.warning("[OCR][TOTALS] Facture %s -> HT=%.2f | TVA=%.2f | TTC=%.2f",
                            move.name, total_ht, total_tva, total_ttc)

            # Nettoyage anciennes lignes PRODUIT uniquement
            product_lines = move.line_ids.filtered(lambda l: l.display_type in (False, "product"))
            product_lines.unlink()

            # Produit placeholder
            product = self.env["product.product"].search([("default_code", "=", "FACTURE_WAITING")], limit=1)
            if not product:
                product = self.env["product.product"].create({
                    "name": "FACTURE EN ATTENTE",
                    "default_code": "FACTURE_WAITING",
                    "type": "service",
                    "lst_price": 0.0,
                })

            # Ajout ligne unique avec total HT
            move.line_ids.create({
                "move_id": move.id,
                "product_id": product.id,
                "name": f"Facture en attente - Total OCR",
                "quantity": 1.0,
                "price_unit": total_ht,
                "account_id": move.journal_id.default_account_id.id,
                "tax_ids": [(6, 0, [t.id for t in self.env["account.tax"].search([("type_tax_use", "=", "purchase")])])]
            })

        return True
