# -*- coding: utf-8 -*-
#account_move.py

import base64
import json
import logging
import re
import subprocess
import unicodedata
from datetime import date, datetime

from odoo import models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


MONTHS_FR_MAP = {
    # sans accents
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

    mindee_local_response = fields.Text(
        string="Réponse OCR JSON (Tesseract)",
        readonly=True,
        store=True,
    )

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
            vals['quantity'] = float(mqty.group(1).replace(',', '.'))
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

    def action_ocr_fetch(self):
        for move in self:
            _logger.warning("⚡ [OCR] Start OCR for move id=%s name=%s", move.id, move.name)
            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = pdf_attachments[0]
            file_path = "/tmp/ocr_temp_file.pdf"
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(attachment.datas))

            venv_python = "/data/odoo/odoo18-venv/bin/python3"
            tesseract_script_path = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/scripts/tesseract_runner.py"
            try:
                result = subprocess.run(
                    [venv_python, tesseract_script_path, file_path],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=180, check=True, encoding="utf-8",
                )
                ocr_json = result.stdout.strip()
                ocr_data = json.loads(ocr_json)
            except Exception as e:
                raise UserError(f"Erreur OCR avec Tesseract : {e}")

            move.mindee_local_response = json.dumps(ocr_data, indent=2, ensure_ascii=False)
            self.env["ir.attachment"].create({
                "name": f"OCR_{attachment.name}.json",
                "res_model": "account.move",
                "res_id": move.id,
                "type": "binary",
                "mimetype": "application/json",
                "datas": base64.b64encode(json.dumps(ocr_data, indent=2).encode("utf-8")),
            })

            parsed = {}
            if ocr_data.get("pages"):
                parsed = ocr_data["pages"][0].get("parsed", {}) or {}
            if parsed.get("invoice_date"):
                norm = self._normalize_date(parsed["invoice_date"])
                if norm:
                    move.invoice_date = norm
            if parsed.get("invoice_number"):
                move.ref = parsed["invoice_number"]

            first_page = ocr_data.get("pages", [{}])[0]
            header_idx = first_page.get("header_index")
            header_line = first_page.get("phrases", [""])[header_idx] if header_idx is not None else ""
            products_raw = first_page.get("products", [])
            products = [ln for ln in products_raw if self._is_real_product_line(header_line, ln)]

            for line_text in products:
                vals = self._parse_product_line(header_line, line_text)

                product = False
                if vals.get('default_code'):
                    product = self.env['product.product'].search([('default_code', '=', vals['default_code'])], limit=1)
                    if not product:
                        product = self.env['product.product'].create({
                            'name': vals['name'],
                            'default_code': vals['default_code'],
                            'type': 'consu'
                        })
                else:
                    product = self.env['product.product'].create({
                        'name': vals['name'],
                        'type': 'consu'
                    })

                line_vals = {
                    'move_id': move.id,
                    'product_id': product.id,
                    'name': vals['name'],
                    'quantity': vals.get('quantity', 1),
                    'price_unit': vals.get('price_unit', 0.0),
                }
                if vals.get('product_uom_id'):
                    line_vals['product_uom_id'] = vals['product_uom_id']

                self.env['account.move.line'].create(line_vals)

        return True
