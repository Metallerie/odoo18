# -*- coding: utf-8 -*-
import os
import base64
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class DocaiAutoImport(models.Model):
    _name = 'docai.ai.invoice.import'
    _description = "Import auto des PDF comptables et analyse via DocAI"

    @api.model
    def import_pdf_invoices(self):
        base_path = "/data/Documents/factures_a_traiter/"
        archive_path = "/data/Documents/factures_archive/" pour corresponde a ce script

        if not os.path.exists(base_path):
            _logger.warning(f"Dossier source introuvable : {base_path}")
            return False

        if not os.path.exists(archive_path):
            os.makedirs(archive_path, exist_ok=True)

        # Journal d'opérations diverses
        journal = self.env['account.journal'].search([
            ('type', '=', 'general')
        ], limit=1)

        if not journal:
            _logger.error("Aucun journal d'opérations diverses trouvé.")
            return False

        for fname in os.listdir(base_path):
            if not fname.lower().endswith(".pdf"):
                continue

            full_path = os.path.join(base_path, fname)

            existing_attachment = self.env['ir.attachment'].search([
                ('name', '=', fname),
                ('res_model', '=', 'account.move'),
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

                # Créer une pièce comptable brouillon
                move = self.env['account.move'].create({
                    'move_type': 'entry',
                    'journal_id': journal.id,
                })

                attachment = self.env['ir.attachment'].create({
                    'name': fname,
                    'datas': base64.b64encode(file_data),
                    'res_model': 'account.move',
                    'res_id': move.id,
                    'type': 'binary',
                    'mimetype': 'application/pdf',
                })

                move.message_post(
                    body="Pièce comptable importée automatiquement via cron (DocAI).",
                    attachment_ids=[attachment.id],
                )

                _logger.info(f"Pièce comptable {move.id} créée avec {fname}")

                try:
                    json_result = attachment.action_parse_docai()
                    if json_result:
                        if 'x_docai_json' in move._fields:
                            move.write({'x_docai_json': json_result})
                        _logger.info(f"Analyse DocAI OK pour {fname}")
                except Exception as e:
                    _logger.error(f"Erreur analyse DocAI {fname} : {e}")

                archived_path = os.path.join(archive_path, fname + "_imported")
                os.rename(full_path, archived_path)

            except Exception as e:
                _logger.error(f"Erreur traitement {fname} : {e}")

        return True
