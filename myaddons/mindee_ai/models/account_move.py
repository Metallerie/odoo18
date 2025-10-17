# -*- coding: utf-8 -*-
# account_move.py (LabelStudio – JSON en base, OCR brut + JSON enrichi, suppression lignes, fournisseur obligatoire, logs debug)

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

    mindee_local_response = fields.Text(
        string="Réponse OCR JSON (Tesseract)",
        readonly=True,
        store=True,
    )

    # ✅ Alias pour compat : certains boutons peuvent appeler action_run_ocr
    def action_run_ocr(self):
        _logger.warning("[OCR] alias action_run_ocr -> action_ocr_fetch")
        return self.action_ocr_fetch()

    def _strip_accents(self, s):
        venv_python = "/data/odoo/odoo18-venv/bin/python3"
        runner_path = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/models/invoice_labelmodel_runner.py"

        for move in self:
            if not move.partner_id:
                raise UserError("Vous devez d'abord renseigner un fournisseur avant de lancer l'OCR.")

            model_json = self._get_partner_labelstudio_json(move.partner_id)
            if not model_json:
                raise UserError(f"Aucun modèle JSON trouvé pour le fournisseur {move.partner_id.display_name}.")

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

            def _pick_zone(labels):
                labels_norm = [self._strip_accents(l).lower() for l in labels]
                for z in zones:
                    lab = self._strip_accents((z.get('label') or '')).lower()
                    if any(lab.startswith(lbl) or lbl in lab for lbl in labels_norm):
                        return (z.get('text') or '').strip()
                return ''

            inv_num = _pick_zone([
                'invoice number', 'numero facture', 'n° facture', 'facture n', 'facture no', 'facture num'
            ])
            if inv_num:
                move.ref = inv_num

            inv_date = _pick_zone(['invoice date', 'date facture', 'date de facture'])
            if inv_date:
                d = self._normalize_date(inv_date)
                if d:
                    move.invoice_date = d

            move.line_ids.unlink()

        return True
