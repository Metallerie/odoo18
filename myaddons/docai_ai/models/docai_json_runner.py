# -*- coding: utf-8 -*-
# docai_json_runner.py
import base64
import os
import json
import logging
from odoo import models, fields, _
from odoo.exceptions import UserError
from google.cloud import documentai_v1 as documentai
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    # JSON complet Document AI (archive pour l’entraînement IA)
    docai_json_raw = fields.Text("JSON complet DocAI", readonly=True)

    # JSON minimal (entities uniquement, exploitable dans Odoo)
    docai_json = fields.Text("JSON simplifié DocAI", readonly=True)

    # Flag pour savoir si la facture a été analysée
    docai_analyzed = fields.Boolean("Analysée par DocAI", default=False, readonly=True)

    # -------------------------------------------------------------------------
    # MÉTHODE PRINCIPALE : Analyse DocAI
    # -------------------------------------------------------------------------
    def action_docai_analyze_attachment(self, force=False):
        """
        Analyse avec Google Document AI.
        - En cron (force=False) : analyse uniquement si JSON absent et pas de total_amount.
        - En manuel (force=True) : réanalyse et écrase les JSON.
        """
        for move in self:
            # ⚡ Skip si déjà analysée ou montant déjà présent
            if (move.docai_analyzed and not force) or (move.amount_total and not force):
                _logger.info(f"[DocAI] Facture {move.id} ignorée (déjà analysée ou total présent)")
                continue

            # 🔎 Récupérer le PDF attaché
            attachment = self.env["ir.attachment"].search([
                ("res_model", "=", "account.move"),
                ("res_id", "=", move.id),
                ("mimetype", "=", "application/pdf")
            ], limit=1)

            if not attachment:
                _logger.warning(f"[DocAI] Aucun PDF trouvé pour facture {move.id}, skip")
                continue

            # ⚙️ Charger config DocAI
            ICP = self.env["ir.config_parameter"].sudo()
            project_id = ICP.get_param("docai_ai.project_id")
            location = ICP.get_param("docai_ai.location", "eu")
            key_path = ICP.get_param("docai_ai.key_path")
            processor_id = ICP.get_param("docai_ai.invoice_processor_id")

            if not all([project_id, location, key_path, processor_id]):
                raise UserError(_("Configuration Document AI incomplète."))

            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
            name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

            try:
                # 🚀 Client Document AI
                client = documentai.DocumentProcessorServiceClient(
                    client_options={"api_endpoint": f"{location}-documentai.googleapis.com"}
                )

                pdf_content = base64.b64decode(attachment.datas)
                raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")
                request = documentai.ProcessRequest(name=name, raw_document=raw_document)
                result = client.process_document(request=request)

                # 📦 JSON complet
                raw_json = documentai.Document.to_json(result.document)

                # 📦 JSON minimal (entities uniquement)
                parsed = json.loads(raw_json)
                minimal = {"entities": parsed.get("entities", [])}

                # 💾 Écriture uniquement si JSON absent OU mode force
                vals = {}
                if not move.docai_json_raw or force:
                    vals["docai_json_raw"] = raw_json
                if not move.docai_json or force:
                    vals["docai_json"] = json.dumps(minimal, indent=2, ensure_ascii=False)

                if vals:
                    vals["docai_analyzed"] = True
                    move.write(vals)
                    _logger.info(f"✅ Facture {move.id} analysée et sauvegardée par DocAI")
                else:
                    _logger.info(f"ℹ️ Facture {move.id} déjà avec JSON, pas de mise à jour")

            except Exception as e:
                _logger.error(f"❌ Erreur DocAI facture {move.id} : {e}")
                raise UserError(_("Erreur analyse Document AI : %s") % e)

    # -------------------------------------------------------------------------
    # MÉTHODE POUR RAFRAÎCHIR (forcer réanalyse)
    # -------------------------------------------------------------------------
    def action_docai_refresh_json(self):
        """Rafraîchir les JSON même si déjà analysé"""
        return self.action_docai_analyze_attachment(force=True)

    # -------------------------------------------------------------------------
    # MÉTHODE POUR LE CRON
    # -------------------------------------------------------------------------
    @api.model
    def cron_docai_analyze_invoices(self):
        """Méthode appelée par le CRON"""
        moves = self.env["account.move"].search([
            ("move_type", "=", "in_invoice"),
            ("state", "=", "draft"),
            ("docai_analyzed", "=", False),
            ("docai_json", "=", False),
            ("amount_total", "=", 0),
        ], limit=10)

        _logger.info(f"[DocAI CRON] {len(moves)} factures à analyser")
        moves.action_docai_analyze_attachment(force=False)

    # -------------------------------------------------------------------------
    # MÉTHODES DE TÉLÉCHARGEMENT (redirection vers controller)
    # -------------------------------------------------------------------------
    def action_docai_download_json_raw(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/docai/download/{self.id}/raw",
            "target": "self",
        }

    def action_docai_download_json_min(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/docai/download/{self.id}/min",
            "target": "self",
        }


# -------------------------------------------------------------------------
# CONTROLLER POUR LE TÉLÉCHARGEMENT
# -------------------------------------------------------------------------
class DocaiDownloadController(http.Controller):

    @http.route('/docai/download/<int:move_id>/<string:kind>', type='http', auth='user')
    def download_json(self, move_id, kind="min", **kwargs):
        """
        Télécharge le JSON d'une facture
        - kind = "raw" → JSON complet
        - kind = "min" → JSON simplifié
        """
        move = request.env['account.move'].browse(move_id)
        if not move.exists():
            return request.not_found()

        content = move.docai_json_raw if kind == "raw" else move.docai_json
        if not content:
            return request.not_found()

        filename = f"facture_{move.id}_{kind}.json"

        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/json'),
                ('Content-Disposition', f'attachment; filename={filename}')
            ]
        )
