# -*- coding: utf-8 -*-
# account_move.py (intégration LabelStudio – JSON en base, OCR brut + JSON enrichi)

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

FOOTER_TOKENS = {
    "total", "total ht", "total ttc", "total t.v.a", "total tva", "net a payer", "net a paye",
    "base ht", "frais fixes", "net ht", "t.v.a", "tva", "ttc", "acompte", "reste a payer",
    "bon de livraison", "commande", "votre commande", "adresse", "siren", "iban", "bic",
    "siege social", "rcs", "ape", "conditions", "paiement", "eco-part", "escompte",
    "remise", "ventilation", "net a payer"
}

UOM_PATTERN = r"\b(?:PI|ML|KG|M2|U|L|UNITE\(S\)|UNITES|UNITE|UNITÉ\(S\))\b"
PRICE_PATTERN = r"\d{1,3}(?:[ .]\d{3})*[.,]\d{2}"
QTY_PATTERN = r"(?<![0-9])\d{1,5}(?:[.,]\d{1,3})?(?![0-9])"


class AccountMove(models.Model):
    _inherit = "account.move"

    # === Stockage direct en base pour l'IA ===
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

    # (Champ existant) on garde si tu l'utilises déjà ailleurs
    mindee_local_response = fields.Text(
        string="Réponse OCR JSON (Tesseract)",
        readonly=True,
        store=True,
    )

    # === Utils ===
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

    def _match_tax_in_odoo(self, tva_rate):
        try:
            taux = float(tva_rate)
        except Exception:
            return False
        return self.env['account.tax'].search([('amount', '=', taux), ('type_tax_use', '=', 'purchase')], limit=1)

    def _match_uom_in_odoo(self, unit_code):
        if not unit_code:
            return False
        mapping = {
            'PI': 'Unité', 'U': 'Unité', 'ML': 'mètre', 'M': 'mètre', 'KG': 'kg', 'M2': 'm²', 'L': 'Litre'
        }
        label = mapping.get(unit_code.upper())
        if label:
            return self.env['uom.uom'].search([('name', 'ilike', label)], limit=1)
        return False

    def _is_real_product_line(self, header_text, line_text):
        t = self._norm(line_text)
        if not t:
            return False
        for tok in FOOTER_TOKENS:
            if tok in t:
                return False
        has_word = re.search(r"[a-zA-Z]", line_text) is not None
        if not has_word:
            return False
        qty = re.search(QTY_PATTERN, line_text)
        unit = re.search(UOM_PATTERN, line_text.upper())
        price = re.search(PRICE_PATTERN, line_text)
        if qty and (unit or price):
            return True
        return False

    def _parse_product_line(self, header, line_text):
        parts = line_text.split()
        vals = {"name": line_text}
        if 'ref' in (header or '').lower():
            if parts:
                vals['default_code'] = parts[0]
                vals['name'] = " ".join(parts[1:]) or line_text
        mqty = re.search(r"(\d+[.,]?\d*)\s*(PI|ML|KG|M2|U|L)?", line_text)
        if mqty:
            try:
                vals['quantity'] = float(mqty.group(1).replace(',', '.'))
            except Exception:
                pass
            if mqty.group(2):
                uom = self._match_uom_in_odoo(mqty.group(2))
                if uom:
                    vals['product_uom_id'] = uom.id
        mprice = re.findall(PRICE_PATTERN, line_text)
        if mprice:
            try:
                vals['price_unit'] = float(mprice[-1].replace(' ', '').replace(',', '.'))
            except Exception:
                pass
        return vals

    # === Récupération du modèle Label Studio depuis la base ===
    def _get_partner_labelstudio_json(self, partner):
        json_str = (partner.labelstudio_json or '').strip()
        if json_str:
            return json_str
        # fallback : dernière version d'historique (si champ vide sur partner)
        hist = self.env['mindee.labelstudio.history'].sudo().search(
            [('partner_id', '=', partner.id)], order='version_date desc, id desc', limit=1
        )
        if hist and (hist.json_content or '').strip():
            return hist.json_content
        return ''

    # === Action principale ===
    def action_ocr_fetch(self):
        """
        - Pas de fallback Tesseract si pas de modèle LS.
        - Génère et stocke en base : ocr_raw_text + ocr_json_result (zones).
        - Alimente ref + invoice_date si zones correspondantes.
        """
        venv_python = "/data/odoo/odoo18-venv/bin/python3"
        runner_path = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/models/invoice_labelmodel_runner.py"

        for move in self:
            if not move.partner_id:
                continue

            model_json = self._get_partner_labelstudio_json(move.partner_id)
            if not model_json:
                _logger.warning("[OCR][LabelStudio] Aucun modèle JSON pour le partenaire id=%s", move.partner_id.id)
                continue  # pas de modèle => rien faire

            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = pdf_attachments[0]

            # Écrire le PDF et le JSON du modèle dans des fichiers temporaires
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                pdf_path = tmp_pdf.name
                tmp_pdf.write(base64.b64decode(attachment.datas))

            with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8", suffix=".json") as tmp_js:
                json_path = tmp_js.name
                tmp_js.write(model_json)

            # Appel runner
            try:
                result = subprocess.run(
                    [venv_python, runner_path, pdf_path, json_path],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=180, check=True, encoding="utf-8",
                )
                ocr_result = json.loads(result.stdout or '{}')
            except Exception as e:
                _logger.error("[OCR][Runner] Erreur runner: %s | stderr=%s", e, getattr(result, 'stderr', ''))
                raise UserError(f"Erreur OCR avec LabelStudio runner : {e}")

            # Stockage direct en base
            move.ocr_raw_text = ocr_result.get("ocr_raw", "")
            zones = ocr_result.get("ocr_zones", []) or []
            move.ocr_json_result = json.dumps(zones, indent=2, ensure_ascii=False)
            # (optionnel) compat
            move.mindee_local_response = move.ocr_json_result

            # Injection champs clés depuis les zones
            def _pick_zone(labels):
                labels_norm = [self._strip_accents(l).lower() for l in labels]
                for z in zones:
                    lab = self._strip_accents((z.get('label') or '')).lower()
                    if any(lab.startswith(lbl) or lbl in lab for lbl in labels_norm):
                        return (z.get('text') or '').strip()
                return ''

            # Numéro de facture
            inv_num = _pick_zone([
                'invoice number', 'numero facture', 'n° facture', 'facture n', 'facture no', 'facture num'
            ])
            if inv_num:
                move.ref = inv_num

            # Date de facture
            inv_date = _pick_zone(['invoice date', 'date facture', 'date de facture'])
            if inv_date:
                d = self._normalize_date(inv_date)
                if d:
                    move.invoice_date = d

        return True
