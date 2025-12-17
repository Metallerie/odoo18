# -*- coding: utf-8 -*-
# account_move.py (Version attente : ligne unique avec HT + TVA 20%)
# Variante: date comptable = date facture, date d'échéance = date facture (FORCÉ)

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

    ocr_raw_text = fields.Text(string="OCR Brut", readonly=True, store=True)
    ocr_json_result = fields.Text(string="OCR JSON enrichi", readonly=True, store=True)
    mindee_local_response = fields.Text(string="Réponse OCR JSON", readonly=True, store=True)

    # === Utils ===
    def _strip_accents(self, s):
        if not s:
            return s
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")

    def _preclean_text(self, s):
        if not s:
            return s
        s = " ".join(str(s).split())
        s = re.sub(r"\bO(?=\d)", "0", s)  # corriger O -> 0
        return s

    def _normalize_date(self, date_str):
        if not date_str:
            return None
        cleaned = self._preclean_text(date_str)
        cleaned_lc = cleaned.lower()
        cleaned_lc_noacc = self._strip_accents(cleaned_lc)

        # format JJ/MM/AAAA ou JJ-MM-AAAA
        m = re.search(r"(?P<d>\d{1,2})[\/-](?P<m>\d{1,2})[\/-](?P<y>\d{2,4})", cleaned_lc_noacc)
        if m:
            try:
                dd, mm, yy = int(m.group("d")), int(m.group("m")), int(m.group("y"))
                if yy < 100:
                    yy = 2000 + yy if yy <= 69 else 1900 + yy
                return date(yy, mm, dd)
            except Exception:
                return None
        return None

    def _to_float(self, val):
        """Convertit texte OCR en float robuste"""
        if not val:
            return 0.0
        val = str(val).strip()
        m = re.findall(r"\d[\d\s.,]*", val)
        if m:
            val = m[-1]  # dernier nombre trouvé
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
        return hist.json_content if hist and hist.json_content else ''

    def _force_accounting_and_due_dates_from_invoice_date(self, move):
        """FORCE: date comptable + échéance = date de facture."""
        inv_date = move.invoice_date
        if not inv_date:
            return
        move.date = inv_date
        move.invoice_date_due = inv_date

    # === Main OCR Fetch ===
    def action_ocr_fetch(self):
        venv_python = "/data/odoo/odoo18-venv/bin/python3"
        runner_path = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/models/invoice_labelmodel_runner.py"

        for move in self:
            if not move.partner_id:
                raise UserError("⚠️ Fournisseur manquant avant OCR.")

            model_json = self._get_partner_labelstudio_json(move.partner_id)
            if not model_json:
                raise UserError(f"⚠️ Aucun modèle JSON pour {move.partner_id.display_name}.")

            # --- Extraire PDF attaché ---
            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("⚠️ Pas de PDF trouvé sur cette facture.")
            attachment = pdf_attachments[0]

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
                    timeout=180, check=True, encoding="utf-8"
                )
                _logger.warning("[OCR][Runner][stdout] %s", result.stdout)
                _logger.warning("[OCR][Runner][stderr] %s", result.stderr)
                if not result.stdout.strip():
                    raise UserError("OCR runner n'a rien renvoyé.")
                ocr_result = json.loads(result.stdout)
            except Exception as e:
                _logger.error("[OCR][Runner][Exception] %s", e)
                raise UserError(f"Erreur OCR : {e}")

            move.ocr_raw_text = ocr_result.get("ocr_raw", "")
            zones = ocr_result.get("ocr_zones", [])
            move.ocr_json_result = json.dumps(zones, indent=2, ensure_ascii=False)
            move.mindee_local_response = move.ocr_json_result

            def _pick_zone(keywords):
                kws = [self._strip_accents(k).lower() for k in keywords]
                for z in zones:
                    lab = self._strip_accents((z.get("label") or "")).lower()
                    if any(k in lab for k in kws):
                        return (z.get("text") or "").strip()
                return ""

            # --- Numéro facture ---
            inv_num = _pick_zone(["invoice number", "numero facture", "facture n"])
            if inv_num:
                inv_num_clean = re.sub(r"facture\s*(n°|no|num)?[:\-]?", "", inv_num, flags=re.I).strip()
                move.ref = inv_num_clean

            # --- Date facture + date comptable + échéance (FORCÉ) ---
            inv_date = _pick_zone(["invoice date", "date facture"])
            if inv_date:
                d = self._normalize_date(inv_date)
                if d:
                    move.invoice_date = d
                    self._force_accounting_and_due_dates_from_invoice_date(move)

            # --- Totaux ---
            total_ht = self._to_float(_pick_zone(["total ht", "brut ht", "net ht"]))
            total_tva = self._to_float(_pick_zone(["total tva", "tva"]))
            total_ttc = self._to_float(_pick_zone(["total ttc", "net a payer", "ttc"]))
            _logger.warning("[OCR][TOTALS] HT=%s TVA=%s TTC=%s", total_ht, total_tva, total_ttc)

            # --- Produit placeholder ---
            product = self.env['product.product'].search([('default_code', '=', 'FACT_WAIT')], limit=1)
            if not product:
                product = self.env['product.product'].create({
                    "name": "Facture en attente",
                    "default_code": "FACT_WAIT",
                    "type": "service",
                })

            # Supprimer anciennes lignes produits
            move.line_ids.filtered(lambda l: l.display_type in (False, 'product')).unlink()

            # TVA fixée à 20%
            tax = self.env['account.tax'].search([
                ('amount', '=', 20),
                ('type_tax_use', '=', 'purchase')
            ], limit=1)

            # Ligne unique
            move.line_ids.create({
                "move_id": move.id,
                "product_id": product.id,
                "name": f"Facture en attente (HT détecté {total_ht})",
                "quantity": 1.0,
                "price_unit": total_ht,
                "account_id": move.journal_id.default_account_id.id,
                "tax_ids": [(6, 0, [tax.id])] if tax else False,
            })

            _logger.info(
                "[OCR][LINES] Facture %s → ligne placeholder créée avec HT=%s TTC=%s",
                move.name, total_ht, total_ttc
            )

        return True
