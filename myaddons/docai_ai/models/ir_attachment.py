# -*- coding: utf-8 -*-
# ir_attachment.py
import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)

class IRAttachment(models.Model):
    _inherit = "ir.attachment"

    # Réponse brute de DocAI
    docai_response_json = fields.Text(
        string="Réponse DocAI (JSON brut)",
        help="Stocke la réponse complète renvoyée par Google Document AI"
    )

    # Type détecté par DocAI (facture fournisseur ou reçu)
    move_type_detected = fields.Selection([
        ("in_invoice", "Facture fournisseur"),
        ("in_receipt", "Reçu"),
    ], string="Type détecté (DocAI)")
