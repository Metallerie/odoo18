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

# ---------------- Heuristiques globales pour filtrer les "faux produits" ----------------
FOOTER_TOKENS = {
    "total", "total ht", "total ttc", "total t.v.a", "total tva", "net a payer", "net a paye",
    "base ht", "frais fixes", "net ht", "t.v.a", "tva", "ttc", "acompte", "reste a payer",
    "bon de livraison", "commande", "votre commande", "adresse", "siren", "iban", "bic",
    "siege social", "rcs", "ape", "conditions", "paiement", "eco-part", "eeco-part", "escompte",
    "remise", "ventilation", "net a payer"
}

UOM_CODES = ("PI", "ML", "KG", "M2", "U", "L")
UOM_PATTERN = r"\b(?:PI|ML|KG|M2|U|L|UNITE\(S\)|UNITES|UNITE|UNITÉ\(S\))\b"
PRICE_PATTERN = r"\d{1,3}(?:[ .]\d{3})*[.,]\d{2}"
QTY_PATTERN = r"\b\d+(?:[.,]\d{1,3})?\b"

class AccountMove(models.Model):
    _inherit = "account.move"

    mindee_local_response = fields.Text(
        string="Réponse OCR JSON (Tesseract)",
        readonly=True,
        store=True,
    )

    # ---------------- Utils ----------------
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
            r"(?P<d>[0-9O]{1,2})\s*[\/]\s*(?P<m>[0-9O]{1,2})\s*[\/]\s*(?P<y>\d{2,4})",
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

    def _normalize_text(self, val):
        return (val or "").strip().lower()

    def _extract_number_and_date(self, text, window=140):
        if not text:
            return (None, None)
        t = self._preclean_text(text)
        num_pat = re.compile(r"\bn(?:[°ºo]|um(?:ero)?)\s*(?P<num>[A-Za-z0-9][\w\-\/\.]*)", re.IGNORECASE)
        date_num_pat = re.compile(r"(?P<d>[0-9O]{1,2})\s*[\/-\.]\s*(?P<m>[0-9O]{1,2})\s*[\/-\.]\s*(?P<y>\d{2,4})")
        date_txt_pat = re.compile(r"(?P<d>[0-9O]{1,2})\s+(?P<mon>[A-Za-z\u00C0-\u017F\.]+)\s+(?P<y>\d{2,4})", re.IGNORECASE)
        for m in num_pat.finditer(t):
            inv_num = m.group("num")
            start = m.end()
            zone = t[start : start + window]
            m_du = re.search(r"\bdu\s+(?P<rest>.+)", zone, re.IGNORECASE)
            zone_scan = m_du.group("rest") if m_du else zone
            m_dn = date_num_pat.search(zone_scan)
            m_dt = date_txt_pat.search(zone_scan)
            if m_dn:
                return (inv_num, f"{m_dn.group('d')}/{m_dn.group('m')}/{m_dn.group('y')}")
            if m_dt:
                return (inv_num, f"{m_dt.group('d')} {m_dt.group('mon')} {m_dt.group('y')}")
        return (None, None)

    # ---------------- Helpers produits ----------------
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
        """Filtre fort pour ne garder que les vraies lignes produit.
        Règles :
         - exclure si tokens de totaux/pieds de page.
         - exiger une quantité ET (unité OU un prix décimal).
         - exiger au moins un mot "long" (désignation) pour éviter les lignes purement numériques.
        """
        t = self._norm(line_text)
        if not t:
            return False
        # 1) Exclusions évidentes
        for tok in FOOTER_TOKENS:
            if tok in t:
                return False
        # 2) Doit avoir une désignation textuelle
        has_word = re.search(r"[a-zA-Z]", line_text) is not None
        if not has_word:
            return False
        # 3) Quantité
        qty = re.search(QTY_PATTERN, line_text)
        # 4) Unité & Prix
        unit = re.search(UOM_PATTERN, line_text.upper())
        price = re.search(PRICE_PATTERN, line_text)
        # Condition minimale : quantité ET (unité OU prix)
        if qty and (unit or price):
            # Bonus : éviter les lignes de type "Ventilation" etc. (déjà gérées par tokens)
            return True
        return False

    def _parse_product_line(self, header, line_text):
        # Parsing léger et robuste
        parts = line_text.split()
        vals = {"name": line_text}
        if 'ref' in (header or '').lower():
            if parts:
                vals['default_code'] = parts[0]
                vals['name'] = " ".join(parts[1:]) or line_text
        # Quantité + UoM
        mqty = re.search(r"(\d+[.,]?\d*)\s*(PI|ML|KG|M2|U|L)?", line_text)
        if mqty:
            vals['quantity'] = float(mqty.group(1).replace(',', '.'))
            if mqty.group(2):
                uom = self._match_uom_in_odoo(mqty.group(2))
                if uom:
                    vals['product_uom_id'] = uom.id
        # Prix unitaire (premier prix décimal rencontré)
        mprice = re.search(PRICE_PATTERN, line_text)
        if mprice:
            vals['price_unit'] = float(mprice.group(0).replace(' ', '').replace(',', '.'))
        return vals

    # ---------------- Main action ----------------
    def action_ocr_fetch(self):
        for move in self:
            _logger.warning("⚡ [OCR] Start OCR for move id=%s name=%s", move.id, move.name)

            # 1) Récup PDF
            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = pdf_attachments[0]
            file_path = "/tmp/ocr_temp_file.pdf"
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(attachment.datas))

            # 2) OCR
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

            # 3) Sauvegarde JSON
            move.mindee_local_response = json.dumps(ocr_data, indent=2, ensure_ascii=False)
            self.env["ir.attachment"].create({
                "name": f"OCR_{attachment.name}.json",
                "res_model": "account.move",
                "res_id": move.id,
                "type": "binary",
                "mimetype": "application/json",
                "datas": base64.b64encode(json.dumps(ocr_data, indent=2).encode("utf-8")),
            })

            # 4) Métadonnées facture
            parsed = {}
            if ocr_data.get("pages"):
                parsed = ocr_data["pages"][0].get("parsed", {}) or {}
            if parsed.get("invoice_date"):
                norm = self._normalize_date(parsed["invoice_date"])
                if norm:
                    move.invoice_date = norm
            if parsed.get("invoice_number"):
                move.ref = parsed["invoice_number"]

            # 5) Lignes produits (filtrage fort)
            first_page = ocr_data.get("pages", [{}])[0]
            header_idx = first_page.get("header_index")
            header_line = first_page.get("phrases", [""])[header_idx] if header_idx is not None else ""
            products_raw = first_page.get("products", [])

            # Appliquer filtre pour ne garder que les vraies lignes produit
            products = [ln for ln in products_raw if self._is_real_product_line(header_line, ln)]

            for line_text in products:
                vals = self._parse_product_line(header_line, line_text)

                # 5.1 Chercher / créer produit
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

                # 5.2 Créer ligne de facture
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
