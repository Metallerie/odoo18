# -*- coding: utf-8 -*-
from odoo import models, api
import os
import base64
import logging

_logger = logging.getLogger(__name__)

class MindeeAutoImport(models.Model):
    _name = 'mindee.ai.invoice.import'
    _description = "Import auto des factures PDF en brouillon"

    @api.model
    def import_pdf_invoices(self):
        base_path = "/data/Documents/factures_a_traiter/"
        archive_path = "/data/Documents/factures_archive/"

        if not os.path.exists(base_path):
            _logger.warning(f"Dossier source introuvable : {base_path}")
            return False

        for fname in os.listdir(base_path):
            if fname.lower().endswith(".pdf"):
                full_path = os.path.join(base_path, fname)
                try:
                    with open(full_path, "rb") as f:
                        file_data = f.read()

                    # Créer la facture vide en brouillon
                    invoice = self.env['account.move'].create({
                        'move_type': 'in_invoice',
                        'state': 'draft',
                        # optionnel : tu peux mettre une journal ou partenaire ici
                        # 'journal_id': ...,
                        # 'partner_id': ...,
                    })

                    # Créer la pièce jointe liée
                    attachment = self.env['ir.attachment'].create({
                        'name': fname,
                        'datas': base64.b64encode(file_data),
                        'res_model': 'account.move',
                        'res_id': invoice.id,
                        'type': 'binary',
                        'mimetype': 'application/pdf',
                    })

                    # Poste un message pour loger l’action
                    invoice.message_post(
                        body="Facture importée automatiquement via cron.",
                        attachment_ids=[attachment.id],
                    )

                    _logger.info(f"Facture ID {invoice.id} créée avec pièce jointe : {fname}")

                    # Archiver le fichier
                    archived_path = os.path.join(archive_path, fname + "_imported")
                    os.rename(full_path, archived_path)

                except Exception as e:
                    _logger.error(f"Erreur lors du traitement du fichier {fname} : {e}")

        return True
