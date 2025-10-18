# -*- coding: utf-8 -*-
import io
import logging
from odoo import models, fields, api
from PyPDF2 import PdfReader

_logger = logging.getLogger(__name__)

class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    move_type_detected = fields.Selection([
        ('in_invoice', "Facture Fournisseur"),
        ('in_receipt', "Reçu Fournisseur"),
    ], string="Type DocAI", readonly=True)

    @api.model
    def create(self, vals):
        """Lorsqu'un attachement est créé → détecter si c'est une facture A4 ou un reçu ticket"""
        attachment = super().create(vals)
        if attachment.mimetype == "application/pdf":
            move_type = attachment._detect_doc_type()
            if move_type:
                attachment.move_type_detected = move_type
        return attachment

    def _detect_doc_type(self):
        """Détecte le type de document (facture A4 ou reçu ticket)"""
        self.ensure_one()
        try:
            # Charger le binaire du PDF
            pdf_data = self._file_read(self.store_fname)
            reader = PdfReader(io.BytesIO(pdf_data))
            page = reader.pages[0]
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)

            # Log dimensions
            _logger.info(f"[DocAI] Dimensions PDF {self.name} : {width} x {height}")

            # Heuristique simple : A4 ~ 595 x 842 points
            if width > 500 and height > 800:
                move_type = "in_invoice"
            else:
                move_type = "in_receipt"

            _logger.info(f"[DocAI] {self.name} détecté comme {move_type}")
            return move_type
        except Exception as e:
            _logger.error(f"Erreur détection type DocAI sur {self.name} : {e}")
            return None
