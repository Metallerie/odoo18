# -*- coding: utf-8 -*-
# account_move.py – OCR Factures (LabelStudio – JSON en base, Totaux HT/TVA/TTC)

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

# Mois FR -> Numéro
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

    # Champs OCR
    ocr_raw_text = fields.Text("OCR Brut (Tesseract)", readonly=True, store=True)
    ocr_json_result = fields.Text("OCR JSON enrichi (LabelStudio)", readonly=True, store=True)
    mindee_local_response = fields.Text("Réponse OCR JSON (Tesseract)", readonly=True, store=True)

    # Utils
    def _strip_accents(self, s):
        if not s:
            return s
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")

    def _preclean_text(self, s):
        if not s:
            return s
        s = " ".join(str(s).split())
        s = re.sub(r"\bO(?=\d)", "0", s)  # O -> 0
        s = re.sub(r"(?<=\d)[Il](?=\d)", "1", s)  # I/l -> 1
        s = s.replace("-", "/").replace(".", "/")
        return s

    def _normalize_date(self, date_str):
        """Convertit une date OCR texte en objet date"""
        if not date_str:
            return None
        raw = str(date_str).strip()
        cleaned = self._preclean_text(raw)
        cleaned_lc = cleaned.lower()
        cleaned_noacc = self._strip_accents(cleaned_lc)

        # Format 01/02/2025
        m = re.search(r"(?P<d>[0-9O]{1,2})[\/-](?P<m>[0-9O]{1,2})[\/-](?P<y>\d{2,4})", cleaned_noacc)
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

        # Format 01 février 2025
        m2 = re.search(r"(?P<d>[0-9O]{1,2})\s+(?P<mon>[a-zA-Z\.]+)\s+(?P<y>\d{2,4})", cleaned_noacc)
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

        _logger.warning("[OCR][DATE] Impossible de parser '%s' -> '%s'", date_str, cleaned)
        return None

    def _get_partner_labelstudio_json(self, partner):
        """Récupère le modèle JSON d’un fournisseur"""
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
        """Convertit proprement texte -> float"""
        if not val:
            return 0.0
        val = val.replace(" ", "").replace(",", ".")
        if not re.match(r"^-?\d+(\.\d+)?$", val):
            return 0.0
        try:
            return float(val)
        except Exception:
            return 0.0

    def _find_tax(self, vat_rate):
        """Trouve une taxe d’achat correspondant au taux OCR"""
        if vat_rate <= 0:
            return False
        tax = self.env['account.tax'].search([
            ('amount', '=', vat_rate),
            ('type_tax_use', '=', 'purchase')
        ], limit=1)
        return tax or False

    # === Action OCR ===
    def action_ocr_fetch(self):
        """OCR + création ligne 'produit en attente' avec totaux"""
        venv_python = "/data/odoo/odoo18-venv/bin/python3"
        runner_path = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/models/invoice_labelmodel_runner.py"

        for move in self:
            if not move.partner_id:
                raise UserError("⚠️ Fournisseur requis avant OCR.")

            model_json = self._get_partner_labelstudio_json(move.partner_id)
            if not model_json:
                raise UserError(f"⚠️ Pas de modèle JSON trouvé pour {move.partner_id.display_name}.")

            # Récup pièce jointe PDF
            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("⚠️ Aucune pièce jointe PDF trouvée.")
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
                _logger.warning("[OCR][Runner][STDOUT] %s", result.stdout)
                _logger.warning("[OCR][Runner][STDERR] %s", result.stderr)

                if not result.stdout.strip():
                    raise UserError("⚠️ Runner OCR vide.")
                ocr_result = json.loads(result.stdout)
            except Exception as e:
                _logger.error("[OCR][Runner][EXCEPTION] %s", e)
                raise UserError(f"Erreur OCR runner : {e}")

            # Sauvegarde résultats OCR
            move.ocr_raw_text = ocr_result.get("ocr_raw", "")
            zones = ocr_result.get("ocr_zones", []) or []
            move.ocr_json_result = json.dumps(zones, indent=2, ensure_ascii=False)
            move.mindee_local_response = move.ocr_json_result

            # Helper de zone
            def _pick_zone(labels):
                labels_norm = [self._strip_accents(l).lower() for l in labels]
                for z in zones:
                    lab = self._strip_accents((z.get('label') or '')).lower()
                    if any(lbl in lab for lbl in labels_norm):
                        return (z.get('text') or '').strip()
                return ''

            # === N° de facture ===
            inv_num = _pick_zone(['invoice number', 'numero facture', 'n° facture', 'facture'])
            if inv_num:
                move.ref = re.sub(r'(?i)facture\s*(n°|no|num|number)?\s*[:\-]?\s*', '', inv_num).strip()

            # === Date de facture ===
            inv_date = _pick_zone(['invoice date', 'date facture'])
            if inv_date:
                d = self._normalize_date(inv_date)
                if d:
                    move.invoice_date = d

            # === Détection Totaux ===
            total_ht = 0.0
            total_tva = 0.0
            total_ttc = 0.0
            for z in zones:
                label = (z.get("label") or "").lower()
                text = (z.get("text") or "").strip()
                clean_text = re.sub(r"[^\d,\.]", "", text)

                if "total brut ht" in label or "total ht" in label or "net h.t" in label:
                    total_ht = self._to_float(clean_text)
                elif "total tva" in label:
                    total_tva = self._to_float(clean_text)
                elif "total ttc" in label or "net a payer" in label:
                    total_ttc = self._to_float(clean_text)

            _logger.warning("[OCR][TOTALS] HT=%s | TVA=%s | TTC=%s", total_ht, total_tva, total_ttc)

            # Nettoyage anciennes lignes produit
            product_lines = move.line_ids.filtered(lambda l: l.display_type in (False, 'product'))
            _logger.warning("[OCR][CLEANUP] %s lignes produit supprimées", len(product_lines))
            product_lines.unlink()

            # Création ligne factice produit
            vat_rate = round((total_tva / total_ht) * 100, 2) if total_ht > 0 and total_tva > 0 else 0.0
            tax = self._find_tax(vat_rate)
            move.line_ids.create({
                "move_id": move.id,
                "name": "Produit en attente (OCR)",
                "quantity": 1,
                "price_unit": total_ht if total_ht else 0.0,
                "account_id": move.journal_id.default_account_id.id,
                "tax_ids": [(6, 0, [tax.id])] if tax else False,
            })

            # Ajout ligne note
            note_text = f"Totaux OCR : HT={total_ht} / TVA={total_tva} / TTC={total_ttc}"
            move.line_ids.create({
                "move_id": move.id,
                "name": note_text,
                "display_type": "line_note",
            })

        return True
