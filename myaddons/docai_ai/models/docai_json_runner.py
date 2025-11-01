# -*- coding: utf-8 -*-
# docai_json_runner.py

import base64
import os
import json
import logging
from io import BytesIO

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from google.cloud import documentai_v1 as documentai
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    docai_json_raw = fields.Text("JSON complet DocAI", readonly=True)
    docai_json = fields.Text("JSON simplifié DocAI", readonly=True)
    docai_analyzed = fields.Boolean("Analysée par DocAI", default=False, readonly=True)

    # -------------------------------------------------------------------------
    # Essai avec un processor donné
    # -------------------------------------------------------------------------
    def _try_processor(self, pdf_content, processor_id, label, project_id, location, key_path):
        """Tente une analyse avec un processor spécifique"""
        try:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
            client = documentai.DocumentProcessorServiceClient(
                client_options={"api_endpoint": f"{location}-documentai.googleapis.com"}
            )

            raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")
            request = documentai.ProcessRequest(
                name=f"projects/{project_id}/locations/{location}/processors/{processor_id}",
                raw_document=raw_document
            )
            result = client.process_document(request=request)

            raw_json = documentai.Document.to_json(result.document)
            parsed = json.loads(raw_json)

            if not parsed.get("entities"):
                _logger.warning(f"[DocAI] {label} → pas d’entités trouvées")
                return None, None

            minimal = {"entities": parsed.get("entities", [])}
            return raw_json, json.dumps(minimal, indent=2, ensure_ascii=False)

        except Exception as e:
            _logger.warning(f"[DocAI] {label} → erreur {e}")
            return None, None

    # -------------------------------------------------------------------------
    # Cascade d’analyse : facture, ticket, etc.
    # -------------------------------------------------------------------------
    def analyze_with_fallback(self, pdf_content):
        ICP = self.env["ir.config_parameter"].sudo()
        project_id = ICP.get_param("docai_ai.project_id")
        location = ICP.get_param("docai_ai.location", "eu")
        key_path = ICP.get_param("docai_ai.key_path")
        invoice_processor = ICP.get_param("docai_ai.invoice_processor_id")
        expense_processor = ICP.get_param("docai_ai.expense_processor_id")

        if not all([project_id, location, key_path, invoice_processor, expense_processor]):
            raise UserError(_("Configuration Document AI incomplète."))

        # 1. Essayer Facture
        raw_json, minimal = self._try_processor(pdf_content, invoice_processor, "Facture", project_id, location, key_path)
        if raw_json:
            return raw_json, minimal, "Facture"

        # 2. Sinon → Ticket de caisse
        raw_json, minimal = self._try_processor(pdf_content, expense_processor, "Ticket de caisse", project_id, location, key_path)
        if raw_json:
            return raw_json, minimal, "Ticket de caisse"

        # 3. Plus tard → autres processors (Kbis, RIB, etc.)

        raise UserError(_("Aucun processor n’a pu analyser le document."))

    # -------------------------------------------------------------------------
    # Méthode principale : analyse DocAI
    # -------------------------------------------------------------------------
    def action_docai_analyze_attachment(self, force=False):
        for move in self:
            if (move.docai_analyzed and not force) or (move.amount_total and not force):
                _logger.info(f"[DocAI] Document {move.id} ignoré (déjà analysé ou total présent)")
                continue

            # Attachement PDF
            attachment = self.env["ir.attachment"].search([
                ("res_model", "=", "account.move"),
                ("res_id", "=", move.id),
                ("mimetype", "=", "application/pdf")
            ], limit=1)

            if not attachment:
                _logger.warning(f"[DocAI] Aucun PDF trouvé pour document {move.id}, skip")
                continue

            pdf_content = base64.b64decode(attachment.datas)

            try:
                # Cascade d’analyse
                raw_json, minimal, label = self.analyze_with_fallback(pdf_content)

                vals = {}
                if not move.docai_json_raw or force:
                    vals["docai_json_raw"] = raw_json
                if not move.docai_json or force:
                    vals["docai_json"] = minimal

                if vals:
                    vals["docai_analyzed"] = True
                    move.write(vals)
                    _logger.info(f"✅ {label} {move.id} analysé et sauvegardé par DocAI")
                else:
                    _logger.info(f"ℹ️ {label} {move.id} déjà avec JSON, pas de mise à jour")

            except Exception as e:
                _logger.error(f"❌ Erreur DocAI document {move.id} : {e}")
                raise UserError(_("Erreur analyse Document AI : %s") % e)

    # -------------------------------------------------------------------------
    # Rafraîchir (forcer réanalyse)
    # -------------------------------------------------------------------------
    def action_docai_refresh_json(self):
        return self.action_docai_analyze_attachment(force=True)

    # -------------------------------------------------------------------------
    # CRON
    # -------------------------------------------------------------------------
    @api.model
    def cron_docai_analyze_invoices(self):
        moves = self.env["account.move"].search([
            ("move_type", "=", "in_invoice"),
            ("state", "=", "draft"),
            ("docai_analyzed", "=", False),
            ("docai_json", "=", False),
            ("amount_total", "=", 0),
        ], limit=10)

        _logger.info(f"[DocAI CRON] {len(moves)} documents à analyser")
        moves.action_docai_analyze_attachment(force=False)


# -------------------------------------------------------------------------
# Controller téléchargement JSON
# -------------------------------------------------------------------------
class DocaiDownloadController(http.Controller):

    @http.route('/docai/download/<int:move_id>/<string:kind>', type='http', auth='user')
    def download_json(self, move_id, kind="min", **kwargs):
        move = request.env['account.move'].browse(move_id)
        if not move.exists():
            return request.not_found()

        content = move.docai_json_raw if kind == "raw" else move.docai_json
        if not content:
            return request.not_found()

        filename = f"document_{move.id}_{kind}.json"
        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/json'),
                ('Content-Disposition', f'attachment; filename={filename}')
            ]
        )
