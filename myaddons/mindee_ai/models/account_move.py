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
        Product = self.env["product.product"]
        for move in self:
            for page in ocr_data.get("pages", []):
                for row in page.get("products", []):
                    if not row:
                        continue

                    # ⚠️ on suppose row = ["code", "nom", "qte", "unité", "prix", "montant", "TVA"]
                    code = row[0] if len(row) > 0 else None
                    name = row[1] if len(row) > 1 else "Produit OCR"
                    qty = 1.0
                    if len(row) > 2:
                        try:
                            qty = float(row[2].replace(",", "."))
                        except:
                            pass
                    price_unit = 0.0
                    if len(row) > 4:
                        try:
                            price_unit = float(row[4].replace(",", "."))
                        except:
                            pass

                    # --- Cas spécial : Éco-participation ---
                    if "eco-part" in name.lower() or "éco-part" in name.lower():
                        product = Product.search([
                            ("default_code", "=", "ECO-PART")
                        ], limit=1)
                        if not product:
                            product = Product.search([("name", "ilike", "éco-participation")], limit=1)
                        if not product:
                            _logger.error("[OCR][ECO-PART] Produit 'Éco-participation' introuvable")
                            continue
                    else:
                        # Produit normal
                        product = None
                        if code:
                            product = Product.search([("default_code", "=", code)], limit=1)
                        if not product:
                            product = Product.search([("name", "ilike", name)], limit=1)
                        if not product:
                            product = Product.create({
                                "name": name,
                                "default_code": code or False,
                                "type": "consu",
                            })

                    # --- Création ligne facture ---
                    self.env["account.move.line"].create({
                        "move_id": move.id,
                        "product_id": product.id,
                        "name": name,
                        "quantity": qty,
                        "price_unit": price_unit,
                        "account_id": move.journal_id.default_account_id.id,
                    })
