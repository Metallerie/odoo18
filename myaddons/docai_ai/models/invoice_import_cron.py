# -*- coding: utf-8 -*-
import os
import base64
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class DocaiAutoImport(models.Model):
    _name = 'docai.ai.invoice.import'
    _description = "Import auto des factures PDF et analyse via DocAI"

    @api.model
    def import_pdf_invoices(self):
        base_path = "/data/Documents/factures_a_traiter/"
        archive_path = "/data/Documents/factures_archive/"

        if not os.path.exists(base_path):
            _logger.warning(f"Dossier source introuvable : {base_path}")
            return False

        for fname in os.listdir(base_path):
            if not fname.lower().endswith(".pdf"):
                continue

            full_path = os.path.join(base_path, fname)

            # Vérifier si déjà traité
            existing_attachment = self.env['ir.attachment'].search([
                ('name', '=', fname),
                ('res_model', '=', 'account.move')
            ], limit=1)

            if existing_attachment:
                _logger.warning(f"Fichier déjà traité (doublon) : {fname}")
                try:
                    duplicate_path = os.path.join(archive_path, fname + "_duplicate")
                    os.rename(full_path, duplicate_path)
                    _logger.info(f"Déplacé vers : {duplicate_path}")
                except Exception as e:
                    _logger.error(f"Erreur déplacement doublon {fname} : {e}")
                continue

            try:
                with open(full_path, "rb") as f:
                    file_data = f.read()

                # Créer facture fournisseur brouillon
                invoice = self.env['account.move'].create({
                    'move_type': 'in_invoice',
                    'state': 'draft',
                })

                # Attacher le PDF
                attachment = self.env['ir.attachment'].create({
                    'name': fname,
                    'datas': base64.b64encode(file_data),
                    'res_model': 'account.move',
                    'res_id': invoice.id,
                    'type': 'binary',
                    'mimetype': 'application/pdf',
                })

                # Poster un message
                invoice.message_post(
                    body="Facture importée automatiquement via cron (DocAI).",
                    attachment_ids=[attachment.id],
                )

                _logger.info(f"Facture {invoice.id} créée avec {fname}")

                # 🔹 Appel DocAI (sera défini dans ir_attachment.py)
                try:
                    json_result = attachment.action_parse_docai()
                    if json_result:
                        invoice.write({'x_docai_json': json_result})  # champ à ajouter dans account_move
                        _logger.info(f"Analyse DocAI OK pour {fname}")
                except Exception as e:
                    _logger.error(f"Erreur analyse DocAI {fname} : {e}")

                # Déplacer le fichier traité
                archived_path = os.path.join(archive_path, fname + "_imported")
                os.rename(full_path, archived_path)

            except Exception as e:
                _logger.error(f"Erreur traitement {fname} : {e}")

        return True
