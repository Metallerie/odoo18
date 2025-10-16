# -*- coding: utf-8 -*-
import base64
import json
import logging
import os
from odoo import models, fields
from odoo.exceptions import UserError
from . import partner_invoice_labelmodel as pilm

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    mindee_local_response = fields.Text(
        string="OCR JSON structuré",
        readonly=True,
        store=True,
    )

    ocr_raw_text = fields.Text(
        string="OCR brut (zones)",
        readonly=True,
        store=True,
        help="Texte brut issu de l'OCR avec coordonnées et contenu de chaque zone"
    )

    def action_ocr_fetch(self):
        """
        Lance l'OCR guidé par modèle JSON fournisseur
        et enregistre le résultat (JSON + brut) dans la facture.
        """
        for move in self:
            _logger.warning("⚡ [OCR] Start OCR for move id=%s name=%s", move.id, move.name)

            # --- PDF attaché ---
            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = pdf_attachments[0]

            # --- Sauvegarde temporaire du PDF ---
            pdf_path = "/tmp/ocr_temp_file.pdf"
            with open(pdf_path, "wb") as f:
                f.write(base64.b64decode(attachment.datas))

            # --- Recherche du modèle fournisseur ---
            partner_name = move.partner_id.name or "generic"
            model_json_file = f"/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/json/{partner_name}_supplier_library.json"
            if not os.path.exists(model_json_file):
                raise UserError(f"Modèle JSON fournisseur introuvable : {model_json_file}")

            # --- OCR extraction ---
            ocr_data = pilm.extract_cases(pdf_path, model_json_file)

            # --- Sauvegarde OCR structuré ---
            move.mindee_local_response = json.dumps(ocr_data, indent=2, ensure_ascii=False)

            self.env["ir.attachment"].create({
                "name": f"OCR_{attachment.name}.json",
                "res_model": "account.move",
                "res_id": move.id,
                "type": "binary",
                "mimetype": "application/json",
                "datas": base64.b64encode(json.dumps(ocr_data, indent=2).encode("utf-8")),
            })

            # --- Sauvegarde OCR brut ---
            raw_text = pilm.pretty_print_results(ocr_data)
            move.ocr_raw_text = raw_text

            self.env["ir.attachment"].create({
                "name": f"OCR_{attachment.name}.txt",
                "res_model": "account.move",
                "res_id": move.id,
                "type": "binary",
                "mimetype": "text/plain",
                "datas": base64.b64encode(raw_text.encode("utf-8")),
            })

            _logger.warning("✅ [OCR] OCR terminé pour move id=%s", move.id)

        return True
