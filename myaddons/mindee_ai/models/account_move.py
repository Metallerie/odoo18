# -*- coding: utf-8 -*-
import base64
import json
import logging
import re
import subprocess
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
        cleaned_lc_noacc = self._strip_accents(cleaned.lower())

        # format numérique
        m = re.search(r"(?P<d>[0-9O]{1,2})[\/](?P<m>[0-9O]{1,2})[\/](?P<y>\d{2,4})", cleaned_lc_noacc)
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

        # format texte
        m2 = re.search(r"(?P<d>[0-9O]{1,2})\s+(?P<mon>[a-zA-Z\u00C0-\u017F\.]+)\s+(?P<y>\d{2,4})", cleaned.lower())
        if m2:
            d = m2.group("d").replace("O", "0")
            mon = self._strip_accents(m2.group("mon").replace(".", "").lower())
            y = int(m2.group("y"))
            mm = MONTHS_FR_MAP.get(mon)
            if mm:
                if y < 100:
                    y = 2000 + y if y <= 69 else 1900 + y
                return date(y, int(mm), int(d))
        return None

    # ---------------- OCR main action ----------------
    def action_ocr_fetch(self):
        for move in self:
            _logger.warning("⚡ [OCR] Start OCR for move id=%s name=%s", move.id, move.name)

            # 1️⃣ Pièce jointe PDF
            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = pdf_attachments[0]

            file_path = "/tmp/ocr_temp_file.pdf"
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(attachment.datas))

            # 2️⃣ Run OCR script
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
                _logger.exception("[OCR] Error running Tesseract")
                raise UserError(f"Erreur OCR avec Tesseract : {e}")

            # 3️⃣ Sauvegarde JSON
            move.mindee_local_response = json.dumps(ocr_data, indent=2, ensure_ascii=False)

            # 4️⃣ Parse infos principales
            parsed = {}
            if ocr_data.get("pages"):
                parsed = ocr_data["pages"][0].get("parsed", {}) or {}

            vals = {}
            if parsed.get("invoice_date"):
                norm = self._normalize_date(parsed["invoice_date"])
                if norm:
                    vals["invoice_date"] = norm
            if parsed.get("invoice_number"):
                vals["ref"] = parsed["invoice_number"]

            if vals:
                move.write(vals)

            # 5️⃣ Création des lignes depuis OCR
            self._create_invoice_lines_from_ocr(ocr_data)

        return True

    # ---------------- Création lignes ----------------
    def _create_invoice_lines_from_ocr(self, ocr_data):
    """Crée les lignes de facture à partir du JSON OCR Tesseract."""
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

            # 🔎 Cas 1 : l’entête commence par "ref"
            if header and header[0].startswith("ref"):
                ref = row[0]
                designation_parts = []
                for token in row[1:]:
                    if re.search(r"\d", token):
                        break
                    designation_parts.append(token)
                designation = " ".join(designation_parts).strip()

            # 🔎 Cas 2 : l’entête commence par "désignation"
            elif header and header[0].startswith("desi"):
                ref = ""
                designation_parts = []
                for token in row:
                    if re.search(r"\d", token):
                        break
                    designation_parts.append(token)
                designation = " ".join(designation_parts).strip()

            else:
                # fallback : tout est dans la ligne
                ref = ""
                designation = " ".join(row)

            # 🔎 Cas particulier Éco-participation
            if re.search(r"eco[- ]?part", designation, re.IGNORECASE):
                eco_prod = Product.search([("name", "ilike", "eco participation")], limit=1)
                if eco_prod:
                    product = eco_prod
                else:
                    # Si produit absent, on crée une seule fois
                    product = Product.create({
                        "name": "ECO PARTICIPATION",
                        "type": "service",
                        "invoice_policy": "order",
                    })
                qty, price_unit = 1, 0.0
                if len(row) >= 2:
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

            # 🔎 Extraction des nombres (quantité / prix / montant)
            numbers = [t for t in row if re.match(r"^\d+[.,]?\d*$", t) or re.match(r"^\d+[.,]\d{2}$", t)]
            qty, price_unit = 1, 0.0

            if len(numbers) == 1:
                try:
                    price_unit = float(numbers[0].replace(",", "."))
                except Exception:
                    price_unit = 0.0
            elif len(numbers) >= 2:
                try:
                    qty = float(numbers[-3].replace(",", ".")) if len(numbers) >= 3 else 1
                except Exception:
                    qty = 1
                try:
                    price_unit = float(numbers[-2].replace(",", "."))
                except Exception:
                    price_unit = 0.0

            # 🔎 Recherche produit par référence ou nom
            product = False
            if ref:
                product = Product.search([("default_code", "=", ref)], limit=1)
            if not product:
                product = Product.search([("name", "ilike", designation)], limit=1)

            if not product:
                product = Product.create({
                    "name": designation,
                    "default_code": ref or "",
                    "type": "product",
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
            _logger.warning("[OCR] %s lignes ajoutées sur la facture %s", len(line_vals), move.name)
