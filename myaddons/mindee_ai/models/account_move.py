import re
import json
import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    ocr_raw = fields.Text("OCR Brut")
    ocr_json = fields.Text("OCR JSON")

    def action_run_ocr(self):
        for move in self:
            pdf_path = move._get_pdf_path()
            partner = move.partner_id
            if not pdf_path or not partner:
                continue

            try:
                # 1. Lancer le runner OCR/LabelStudio
                from .invoice_labelmodel_runner import run_invoice_ocr
                ocr_zones = run_invoice_ocr(pdf_path, partner)

                # 2. Extraire les infos avec regex plus costaud
                invoice_number = self._extract_invoice_number(ocr_zones)
                invoice_date = self._extract_invoice_date(ocr_zones)

                # 3. Enregistrer les infos principales
                move.ref = invoice_number
                move.invoice_date = invoice_date if invoice_date else move.invoice_date

                # 4. Stocker les résultats OCR
                # OCR JSON : tout le détail zones+coords
                move.ocr_json = json.dumps(ocr_zones, ensure_ascii=False, indent=2)

                # OCR brut : version lisible ligne par ligne
                raw_lines = []
                for zone in ocr_zones:
                    raw_lines.append(f"[{zone['label']}] {zone['text']}")
                move.ocr_raw = "\n".join(raw_lines)

            except Exception as e:
                _logger.error(f"[OCR][Runner][EXCEPTION] {str(e)}", exc_info=True)

    # -------------------
    # Regex plus robustes
    # -------------------
    def _extract_invoice_number(self, zones):
        """
        Cherche le numéro de facture avec plusieurs patterns
        """
        patterns = [
            r"FACTURE\s*N°\s*:?[\s]*([0-9]+)",
            r"Facture\s*:?[\s]*([0-9]+)",
            r"N°\s*Facture\s*:?[\s]*([0-9]+)",
        ]
        for z in zones:
            text = z.get("text", "")
            for p in patterns:
                m = re.search(p, text, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
        return ""

    def _extract_invoice_date(self, zones):
        """
        Cherche une date au format JJ/MM/AAAA
        """
        date_pattern = r"([0-9]{2}/[0-9]{2}/[0-9]{4})"
        for z in zones:
            text = z.get("text", "")
            m = re.search(date_pattern, text)
            if m:
                return m.group(1)
        return ""
