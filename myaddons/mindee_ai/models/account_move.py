# -*- coding: utf-8 -*-
# account_move.py (OCR simplifié – enregistrement uniquement des totaux + ligne produit "en attente")

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

    ocr_raw_text = fields.Text(string="OCR Brut (Tesseract)", readonly=True, store=True)
    ocr_json_result = fields.Text(string="OCR JSON enrichi (LabelStudio)", readonly=True, store=True)
    mindee_local_response = fields.Text(string="Réponse OCR JSON (Tesseract)", readonly=True, store=True)

    def _strip_accents(self, s):
        if not s:
            return s
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")

    def _to_float(self, val):
        """Convertit un texte OCR en float sécurisé"""
        if not val or val == "NUL":
            return 0.0
        val = val.replace(" ", "").replace(",", ".")
        try:
            return float(val)
        except Exception:
            return 0.0

    def action_ocr_fetch(self):
        venv_python = "/data/odoo/odoo18-venv/bin/python3"
        runner_path = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/models/invoice_labelmodel_runner.py"

        for move in self:
            if not move.partner_id:
                raise UserError("Vous devez d'abord renseigner un fournisseur avant de lancer l'OCR.")

            # Charger modèle JSON fournisseur
            model_json = (move.partner_id.labelstudio_json or '').strip()
            if not model_json:
                raise UserError(f"Aucun modèle JSON trouvé pour le fournisseur {move.partner_id.display_name}.")

            # Récupération du PDF
            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = pdf_attachments[0]

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                pdf_path = tmp_pdf.name
                tmp_pdf.write(base64.b64decode(attachment.datas))

            with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8", suffix=".json") as tmp_js:
                json_path = tmp_js.name
                tmp_js.write(model_json)

            # Exécution runner
            try:
                result = subprocess.run(
                    [venv_python, runner_path, pdf_path, json_path],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=180, check=True, encoding="utf-8",
                )
                _logger.warning("[OCR][Runner] stdout=%s", result.stdout)
                _logger.warning("[OCR][Runner] stderr=%s", result.stderr)

                if not result.stdout.strip():
                    raise UserError("Runner n'a rien renvoyé, voir logs pour debug.")

                ocr_result = json.loads(result.stdout)
            except Exception as e:
                _logger.error("[OCR][Runner][EXCEPTION] %s", e)
                raise UserError(f"Erreur OCR avec LabelStudio runner : {e}")

            move.ocr_raw_text = ocr_result.get("ocr_raw", "")
            zones = ocr_result.get("ocr_zones", []) or []
            move.ocr_json_result = json.dumps(zones, indent=2, ensure_ascii=False)
            move.mindee_local_response = move.ocr_json_result

            # --- Extraction des totaux ---
            total_ht = 0.0
            total_tva = 0.0
            total_ttc = 0.0

            for z in zones:
                label = (z.get("label") or "").lower()
                text = (z.get("text") or "").strip()
                if "total ht" in label or "net h.t" in text.lower():
                    total_ht = self._to_float(text)
                elif "tva" in label or "total tva" in text.lower():
                    total_tva = self._to_float(text)
                elif "ttc" in label or "net a payer" in text.lower():
                    total_ttc = self._to_float(text)

            _logger.info("[OCR][TOTALS] HT=%s, TVA=%s, TTC=%s", total_ht, total_tva, total_ttc)

            # Nettoyage des anciennes lignes
            product_lines_to_remove = move.line_ids.filtered(lambda l: l.display_type in (False, 'product'))
            product_lines_to_remove.unlink()

            # Produit d'attente
            product_attente = self.env.ref("mindee_ai.product_facture_attente", raise_if_not_found=False)
            account_id = move.journal_id.default_account_id.id
            tax = self.env['account.tax'].search([('amount', '=', total_tva), ('type_tax_use', '=', 'purchase')], limit=1)

            move.line_ids.create({
                "move_id": move.id,
                "name": "Facture OCR – en attente",
                "quantity": 1.0,
                "price_unit": total_ht if total_ht > 0 else total_ttc,
                "account_id": account_id,
                "tax_ids": [(6, 0, [tax.id])] if tax else False,
                "product_id": product_attente.id if product_attente else False,
            })

        return True
