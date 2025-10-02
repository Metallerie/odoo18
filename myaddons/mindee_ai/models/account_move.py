# -*- coding: utf-8 -*-
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
                mon_key = self._strip_accents(m2.group("mon").lower().replace(".", ""))
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
        num_pat = re.compile(
            r"\bn(?:[°ºo]|um(?:ero)?)\s*(?P<num>[A-Za-z0-9][\w\-\/\.]*)",
            re.IGNORECASE,
        )
        date_num_pat = re.compile(
            r"(?P<d>[0-9O]{1,2})[\/\-\.](?P<m>[0-9O]{1,2})[\/\-\.](?P<y>\d{2,4})"
        )
        date_txt_pat = re.compile(
            r"(?P<d>[0-9O]{1,2})\s+(?P<mon>[A-Za-z\u00C0-\u017F\.]+)\s+(?P<y>\d{2,4})",
            re.IGNORECASE,
        )
        for m in num_pat.finditer(t):
            inv_num = m.group("num")
            start = m.end()
            zone = t[start:start + window]
            m_dn = date_num_pat.search(zone)
            m_dt = date_txt_pat.search(zone)
            if m_dn:
                return (inv_num, f"{m_dn.group('d')}/{m_dn.group('m')}/{m_dn.group('y')}")
            if m_dt:
                return (inv_num, f"{m_dt.group('d')} {m_dt.group('mon')} {m_dt.group('y')}")
        return (None, None)

    # ---------------- OCR Fetch ----------------
    def action_ocr_fetch(self):
        for move in self:
            _logger.warning("⚡ [OCR] Start OCR for move %s", move.name)

            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée.")
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
                _logger.exception("[OCR] Script error")
                raise UserError(f"Erreur OCR : {e}")

            move.mindee_local_response = json.dumps(ocr_data, indent=2, ensure_ascii=False)
            self.env["ir.attachment"].create({
                "name": f"OCR_{attachment.name}.json",
                "res_model": "account.move",
                "res_id": move.id,
                "type": "binary",
                "mimetype": "application/json",
                "datas": base64.b64encode(json.dumps(ocr_data, indent=2).encode("utf-8")),
            })

            # Appliquer les données
            parsed = {}
            if ocr_data.get("pages"):
                parsed = ocr_data["pages"][0].get("parsed", {}) or {}

            if not parsed.get("invoice_number") or not parsed.get("invoice_date"):
                phrases = []
                for p in ocr_data.get("pages", []):
                    phrases.extend(p.get("phrases", []))
                raw_text_clean = self._preclean_text(" ".join(phrases))
                inv_num, inv_date_raw = self._extract_number_and_date(raw_text_clean, window=160)
                if inv_num and not parsed.get("invoice_number"):
                    parsed["invoice_number"] = inv_num
                if inv_date_raw and not parsed.get("invoice_date"):
                    parsed["invoice_date"] = inv_date_raw

            vals = {}
            if parsed.get("invoice_date"):
                norm = self._normalize_date(parsed["invoice_date"])
                if norm:
                    vals["invoice_date"] = norm
            if parsed.get("invoice_number"):
                vals["ref"] = parsed["invoice_number"]
            if vals:
                move.write(vals)

            # Création des lignes de facture
            move._create_invoice_lines_from_ocr(ocr_data)

        return True

    # ---------------- Création lignes facture ----------------
    def _create_invoice_lines_from_ocr(self, ocr_data):
        Product = self.env["product.product"]
        for move in self:
            if not ocr_data.get("pages"):
                continue
            page = ocr_data["pages"][0]
            header = [h.lower() for h in page.get("header", [])]
            products = page.get("products", [])
            line_vals = []
            for row in products:
                if not row:
                    continue

                ref, designation = "", ""
                # Cas entête commence par Ref
                if header and header[0].startswith("ref"):
                    ref = row[0]
                    designation = " ".join(row[1:])
                # Cas entête commence par Désignation
                elif header and header[0].startswith("desi"):
                    designation = " ".join(row)
                else:
                    designation = " ".join(row)

                # Eco-participation
                if re.search(r"eco[- ]?part", designation, re.IGNORECASE):
                    eco_prod = Product.search([("name", "ilike", "eco participation")], limit=1)
                    if eco_prod:
                        product = eco_prod
                        qty, price_unit = 1, 0.0
                        try:
                            price_unit = float(row[-1].replace(",", "."))
                        except Exception:
                            pass
                        line_vals.append({
                            "product_id": product.id,
                            "name": designation,
                            "quantity": qty,
                            "price_unit": price_unit,
                            "account_id": product.property_account_expense_id.id or product.categ_id.property_account_expense_categ_id.id,
                        })
                        continue

                # Extraction nombres
                numbers = [t for t in row if re.match(r"^\d+[.,]?\d*$", t) or re.match(r"^\d+[.,]\d{2}$", t)]
                qty, price_unit = 1, 0.0
                if len(numbers) == 1:
                    try:
                        price_unit = float(numbers[0].replace(",", "."))
                    except Exception:
                        pass
                elif len(numbers) >= 2:
                    try:
                        qty = float(numbers[-3].replace(",", ".")) if len(numbers) >= 3 else 1
                    except Exception:
                        pass
                    try:
                        price_unit = float(numbers[-2].replace(",", "."))
                    except Exception:
                        pass

                # Recherche produit
                product = False
                if ref:
                    product = Product.search([("default_code", "=", ref)], limit=1)
                if not product:
                    product = Product.search([("name", "ilike", designation)], limit=1)
                if not product:
                    product = Product.create({
                        "name": designation,
                        "default_code": ref or "",
                        "type": "consu",   # ⚠️ "consu" pour éviter l'erreur
                    })

                line_vals.append({
                    "product_id": product.id,
                    "name": designation,
                    "quantity": qty,
                    "price_unit": price_unit,
                    "account_id": product.property_account_expense_id.id or product.categ_id.property_account_expense_categ_id.id,
                })

            if line_vals:
                move.write({"invoice_line_ids": [(0, 0, vals) for vals in line_vals]})
                _logger.warning("[OCR] %s lignes ajoutées sur facture %s", len(line_vals), move.name)
