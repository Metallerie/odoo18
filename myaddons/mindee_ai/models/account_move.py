# -*- coding: utf-8 -*-
# account_move.py (OCR + détection fournisseur + ligne produit "en attente")

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

    # --- Utilitaires ---
    def _strip_accents(self, s):
        if not s:
            return s
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")

    def _normalize_date(self, date_str):
        if not date_str:
            return None
        raw = str(date_str).strip()
        cleaned = " ".join(raw.split())
        cleaned_lc = cleaned.lower()
        cleaned_lc_noacc = self._strip_accents(cleaned_lc)

        m = re.search(r"(?P<d>[0-9]{1,2})[\/-](?P<m>[0-9]{1,2})[\/-](?P<y>\d{2,4})", cleaned_lc_noacc)
        if m:
            try:
                dd, mm, yy = int(m.group("d")), int(m.group("m")), int(m.group("y"))
                if yy < 100:
                    yy = 2000 + yy if yy <= 69 else 1900 + yy
                return date(yy, mm, dd)
            except Exception:
                pass

        m2 = re.search(r"(?P<d>[0-9]{1,2})\s+(?P<mon>[a-z]+)\s+(?P<y>\d{2,4})", cleaned_lc_noacc)
        if m2:
            try:
                dd, mon, yy = int(m2.group("d")), m2.group("mon"), int(m2.group("y"))
                if yy < 100:
                    yy = 2000 + yy if yy <= 69 else 1900 + yy
                mm = MONTHS_FR_MAP.get(mon)
                if mm:
                    return date(yy, int(mm), dd)
            except Exception:
                pass

        _logger.warning("[OCR][DATE] Parse KO: %s", date_str)
        return None

    def _get_partner_labelstudio_json(self, partner):
        json_str = (partner.labelstudio_json or '').strip()
        if json_str:
            return json_str
        hist = self.env['mindee.labelstudio.history'].sudo().search(
            [('partner_id', '=', partner.id)], order='version_date desc, id desc', limit=1
        )
        return hist.json_content if hist and hist.json_content else ''

    def _to_float(self, val):
        if not val:
            return 0.0
        txt = str(val).replace(" ", "").replace(",", ".")
        try:
            return float(re.sub(r"[^\d.\-]", "", txt))
        except Exception:
            return 0.0

    def action_ocr_fetch(self):
        venv_python = "/data/odoo/odoo18-venv/bin/python3"
        runner_path = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/models/invoice_labelmodel_runner.py"

        for move in self:
            # --- PDF + modèle JSON ---
            if not move.partner_id:
                _logger.warning("[OCR] Aucun fournisseur défini avant OCR (sera peut-être détecté automatiquement).")

            model_json = self._get_partner_labelstudio_json(move.partner_id) if move.partner_id else ""
            if not model_json:
                _logger.info("[OCR] Pas de modèle JSON LabelStudio défini → tentative avec OCR brut.")

            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée.")
            attachment = pdf_attachments[0]

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                tmp_pdf.write(base64.b64decode(attachment.datas))
                pdf_path = tmp_pdf.name

            with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8", suffix=".json") as tmp_js:
                tmp_js.write(model_json or "[]")
                json_path = tmp_js.name

            # --- Lancer runner ---
            try:
                result = subprocess.run(
                    [venv_python, runner_path, pdf_path, json_path],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=180, check=True, encoding="utf-8",
                )
                _logger.warning("[OCR][Runner][stdout]=%s", result.stdout)
                _logger.warning("[OCR][Runner][stderr]=%s", result.stderr)
                ocr_result = json.loads(result.stdout) if result.stdout.strip() else {}
            except Exception as e:
                raise UserError(f"Erreur OCR runner: {e}")

            move.ocr_raw_text = ocr_result.get("ocr_raw", "")
            zones = ocr_result.get("ocr_zones", [])
            move.ocr_json_result = json.dumps(zones, indent=2, ensure_ascii=False)
            move.mindee_local_response = move.ocr_json_result

            def _pick_zone(labels):
                for z in zones:
                    if z.get("label", "").lower() in [lbl.lower() for lbl in labels]:
                        return (z.get("text") or "").strip()
                return ""

            # --- Numéro + date ---
            inv_num = _pick_zone(["Invoice Number", "Facture", "Numéro facture"])
            if inv_num:
                inv_num_clean = re.sub(r"(?i)facture\s*(n°|no|num|number)?[:\-]?", "", inv_num).strip()
                move.ref = inv_num_clean

            inv_date = _pick_zone(["Invoice Date", "Date facture"])
            if inv_date:
                d = self._normalize_date(inv_date)
                if d:
                    move.invoice_date = d

            # --- Détection fournisseur ---
            supplier_name = _pick_zone(["Supplier", "Supplier NAME"])
            supplier_vat = _pick_zone(["Supplier VAT Number"])
            supplier_siren = _pick_zone(["Supplier BIC"])

            _logger.warning("[OCR][SUPPLIER DETECTED] name=%s | vat=%s | siren=%s",
                            supplier_name, supplier_vat, supplier_siren)

            partner = False
            if supplier_vat:
                partner = self.env["res.partner"].search([("vat", "ilike", supplier_vat)], limit=1)
            if not partner and supplier_siren:
                siren_clean = re.sub(r"\D", "", supplier_siren)
                partner = self.env["res.partner"].search([("siren", "=", siren_clean)], limit=1)
            if not partner and supplier_name:
                partner = self.env["res.partner"].search([("name", "ilike", supplier_name)], limit=1)

            if partner:
                move.partner_id = partner.id
                _logger.info("[OCR][SUPPLIER] Associé à %s (id=%s)", partner.name, partner.id)
            else:
                _logger.warning("[OCR][SUPPLIER] Aucun fournisseur trouvé pour '%s'", supplier_name)

            # --- Totaux ---
            total_ht = self._to_float(_pick_zone(["Total HT", "TOTAL NETH.T", "TOTAL BRUT HT."]))
            total_tva = self._to_float(_pick_zone(["Total TVA", "TVA"]))
            total_ttc = self._to_float(_pick_zone(["Total TTC", "NET A PAYER"]))

            _logger.warning("[OCR][TOTALS] HT=%s | TVA=%s | TTC=%s", total_ht, total_tva, total_ttc)

            # --- Supprimer anciennes lignes produit ---
            move.line_ids.filtered(lambda l: l.display_type in (False, "product")).unlink()

            # --- Produit en attente ---
            wait_product = self.env["product.product"].search([("default_code", "=", "WAITING_OCR")], limit=1)
            if not wait_product:
                wait_product = self.env["product.product"].create({
                    "name": "Produit en attente OCR",
                    "default_code": "WAITING_OCR",
                    "type": "service",
                })

            tax_20 = self.env["account.tax"].search([("amount", "=", 20), ("type_tax_use", "=", "purchase")], limit=1)

            move.line_ids.create({
                "move_id": move.id,
                "product_id": wait_product.id,
                "name": "Facture OCR en attente",
                "quantity": 1,
                "price_unit": total_ht if total_ht else total_ttc,
                "account_id": move.journal_id.default_account_id.id,
                "tax_ids": [(6, 0, [tax_20.id])] if tax_20 else False,
            })

            _logger.info("[OCR][LINES] Ligne d'attente créée : HT=%s / TVA forcée 20%%", total_ht)

        return True
