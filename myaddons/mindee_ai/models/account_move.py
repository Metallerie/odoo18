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
        """Corrige les confusions OCR courantes et normalise l'espace."""
        if not s:
            return s
        # normalisation espace
        s = " ".join(str(s).split())

        # remplacements ciblés chiffres/lettres
        #  O -> 0 lorsqu'il est au début d'un jour/mois (ex: 'O2 Avril 2025')
        s = re.sub(r"\bO(?=\d)", "0", s)
        # I/l entre chiffres -> 1 (ex: '2l' -> '21')
        s = re.sub(r"(?<=\d)[Il](?=\d)", "1", s)
        # tirets/points -> slash pour simplifier le parsing
        s = s.replace("-", "/").replace(".", "/")

        return s

    def _normalize_date(self, date_str):
        """Normalise une date FR (texte ou numérique) vers un objet date.
        Ne dépend PAS du locale. Gère 'O2 Avril 2025', '02/04/2025', '2/4/25', etc.
        """
        if not date_str:
            return None

        raw = str(date_str).strip()
        cleaned = self._preclean_text(raw)
        cleaned_lc = cleaned.lower()
        cleaned_lc_noacc = self._strip_accents(cleaned_lc)

        # 1) formats numériques :  dd/mm/yyyy  | d/m/yy
        m = re.search(
            r"(?P<d>[0-9O]{1,2})\s*[\/]\s*(?P<m>[0-9O]{1,2})\s*[\/]\s*(?P<y>\d{2,4})",
            cleaned_lc_noacc,
        )
        if m:
            d = m.group("d").replace("O", "0")
            mth = m.group("m").replace("O", "0")
            y = m.group("y")
            try:
                dd = int(d)
                mm = int(mth)
                yy = int(y)
                if yy < 100:
                    yy = 2000 + yy if yy <= 69 else 1900 + yy
                return date(yy, mm, dd)
            except Exception:
                pass  # tente le format texte

        # 2) formats texte : dd <mois fr> yyyy
        #    accepte '02 Avril 2025', '2 avr 25', '02 decembre 2025'...
        m2 = re.search(
            r"(?P<d>[0-9O]{1,2})\s+"
            r"(?P<mon>[a-zA-Z\u00C0-\u017F\.]+)\s+"
            r"(?P<y>\d{2,4})",
            cleaned_lc,
        )
        if m2:
            d = m2.group("d").replace("O", "0")
            mon_raw = m2.group("mon").replace(".", "")
            mon_key = self._strip_accents(mon_raw.lower())
            y = m2.group("y")

            mm = MONTHS_FR_MAP.get(mon_key)
            if mm:
                try:
                    dd = int(d)
                    yy = int(y)
                    if yy < 100:
                        yy = 2000 + yy if yy <= 69 else 1900 + yy
                    return date(yy, int(mm), dd)
                except Exception:
                    pass

        _logger.warning("[OCR][DATE] Parse KO: '%s' -> cleaned='%s'", date_str, cleaned)
        return None

    def _normalize_text(self, val):
        return (val or "").strip().lower()

    def _extract_number_and_date(self, text, window=140):
        """Ancre sur 'n°' et essaie de trouver une date dans une fenêtre proche."""
        if not text:
            return (None, None)

        t = self._preclean_text(text)

        # n° / nº / no / n°°
        num_pat = re.compile(
            r"\bn(?:[°ºo]|um(?:ero)?)\s*(?P<num>[A-Za-z0-9][\w\-\/\.]*)",
            re.IGNORECASE,
        )

        # dates possibles (numérique ou texte FR), tolérance 'O' en tête
        date_num_pat = re.compile(
            r"(?P<d>[0-9O]{1,2})\s*[\/\-\.]\s*(?P<m>[0-9O]{1,2})\s*[\/\-\.]\s*(?P<y>\d{2,4})"
        )
        date_txt_pat = re.compile(
            r"(?P<d>[0-9O]{1,2})\s+(?P<mon>[A-Za-z\u00C0-\u017F\.]+)\s+(?P<y>\d{2,4})",
            re.IGNORECASE,
        )

        for m in num_pat.finditer(t):
            inv_num = m.group("num")
            start = m.end()
            zone = t[start : start + window]

            # priorité : motif "du <date>" si présent
            m_du = re.search(r"\bdu\s+(?P<rest>.+)", zone, re.IGNORECASE)
            zone_scan = m_du.group("rest") if m_du else zone

            m_dn = date_num_pat.search(zone_scan)
            m_dt = date_txt_pat.search(zone_scan)

            if m_dn:
                d = m_dn.group("d"); mth = m_dn.group("m"); y = m_dn.group("y")
                candidate = f"{d}/{mth}/{y}"
                return (inv_num, candidate)

            if m_dt:
                d = m_dt.group("d")
                mon = m_dt.group("mon")
                y = m_dt.group("y")
                candidate = f"{d} {mon} {y}"
                return (inv_num, candidate)

        return (None, None)

    # ---------------- Main action ----------------
    def action_ocr_fetch(self):
        for move in self:
            _logger.warning("⚡ [OCR] Start OCR for move id=%s name=%s", move.id, move.name)

            # 1️⃣ Récup PDF
            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = pdf_attachments[0]
            _logger.warning("[OCR] Attachment found: %s", attachment.name)

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
                _logger.warning("[OCR] Script executed successfully")
            except subprocess.CalledProcessError as e:
                _logger.error("[OCR] Script ERROR for %s. STDERR: %s", attachment.name, e.stderr)
                raise UserError(f"Erreur OCR :\n\nSTDERR:\n{e.stderr}\n\nSTDOUT:\n{e.stdout}")
            except Exception as e:
                _logger.exception("[OCR] Unexpected error")
                raise UserError(f"Erreur OCR avec Tesseract : {e}")

            # 3️⃣ Sauvegarde JSON brut
            move.mindee_local_response = json.dumps(ocr_data, indent=2, ensure_ascii=False)
            self.env["ir.attachment"].create({
                "name": f"OCR_{attachment.name}.json",
                "res_model": "account.move",
                "res_id": move.id,
                "type": "binary",
                "mimetype": "application/json",
                "datas": base64.b64encode(json.dumps(ocr_data, indent=2).encode("utf-8")),
            })
            _logger.warning("[OCR] JSON result saved as attachment")

            # 4️⃣ Lecture des données extraites
            parsed = {}
            if ocr_data.get("pages"):
                parsed = ocr_data["pages"][0].get("parsed", {}) or {}

            # 🔎 Texte brut (phrases concaténées) + pré-nettoyage
            phrases = []
            for p in ocr_data.get("pages", []):
                phrases.extend(p.get("phrases", []))
            raw_text = " ".join(phrases)
            raw_text_clean = self._preclean_text(raw_text)

            # 🔎 Extraction ancrée n° + date dans la zone proche
            if not parsed.get("invoice_number") or not parsed.get("invoice_date"):
                inv_num, inv_date_raw = self._extract_number_and_date(raw_text_clean, window=160)
                if inv_num and not parsed.get("invoice_number"):
                    parsed["invoice_number"] = inv_num
                if inv_date_raw and not parsed.get("invoice_date"):
                    parsed["invoice_date"] = inv_date_raw
                _logger.warning("[OCR][ANCHOR] num=%s date_raw=%s", inv_num, inv_date_raw)

            vals = {}
            # 🗓 normalisation date robuste FR
            if parsed.get("invoice_date"):
                norm = self._normalize_date(parsed["invoice_date"])
                if norm:
                    vals["invoice_date"] = norm
                else:
                    _logger.warning("[OCR] Date non normalisée: '%s'", parsed["invoice_date"])

            if parsed.get("invoice_number"):
                vals["ref"] = parsed["invoice_number"]

            _logger.warning("[OCR] Parsed values: %s", parsed)

            # 5️⃣ Application des règles OCR
            rules = self.env["ocr.configuration.rule"].search([("active", "=", True)], order="sequence")

            invoice_number = parsed.get("invoice_number", "") or ""
            invoice_date = parsed.get("invoice_date", "") or ""
            partner_name_ocr = parsed.get("supplier_name", "") or ""

            _logger.warning("[OCR] Checking %s rules", len(rules))

            for rule in rules:
                value = None
                if rule.variable == "partner_name":
                    value = partner_name_ocr or raw_text_clean
                elif rule.variable == "invoice_number":
                    value = invoice_number
                elif rule.variable == "invoice_date":
                    value = invoice_date

                matched = False
                if rule.condition_type == "text" and rule.value_text:
                    val = self._normalize_text(value)
                    cmp = self._normalize_text(rule.value_text)

                    if rule.operator == "contains":
                        matched = cmp in val
                    elif rule.operator == "==":
                        matched = val == cmp
                    elif rule.operator == "startswith":
                        matched = val.startswith(cmp)
                    elif rule.operator == "endswith":
                        matched = val.endswith(cmp)

                    # fallback contains pour les partenaires
                    if rule.variable == "partner_name" and not matched:
                        if cmp in val:
                            matched = True
                            _logger.warning("[OCR][RULE] Fallback contains appliqué pour '%s'", rule.name)

                _logger.warning(
                    "[OCR][RULE] Testing '%s' (var=%s, op=%s, val_text=%s) → %s",
                    rule.name, rule.variable, rule.operator, rule.value_text, matched
                )

                if matched and rule.partner_id:
                    vals["partner_id"] = rule.partner_id.id
                    _logger.warning("[OCR][RULE] MATCHED: '%s' → partner '%s'",
                                    rule.name, rule.partner_id.name)
                    break

            # 6️⃣ Mise à jour facture
            if vals:
                try:
                    move.write(vals)
                    _logger.warning("[OCR] Move updated with: %s", vals)
                except Exception as e:
                    _logger.exception("[OCR] Write error on move %s", move.id)
                    raise UserError(f"Erreur d’écriture dans la facture : {e}")

        return True
