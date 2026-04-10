# -*- coding: utf-8 -*-
# docai_json_runner.py

import base64
import os
import json
import logging
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
    # Outils JSON simplifié
    # -------------------------------------------------------------------------
    def _entity_mention(self, entity):
        """Retourne la valeur texte principale d'une entité."""
        if not entity:
            return None

        mention = entity.get("mentionText")
        if mention not in (None, ""):
            return mention

        normalized = entity.get("normalizedValue", {})
        if normalized.get("text"):
            return normalized.get("text")

        money_value = normalized.get("moneyValue", {})
        units = money_value.get("units")
        nanos = money_value.get("nanos")

        if units is not None and nanos is not None:
            return f"{units}.{str(abs(nanos)).zfill(9)[:2]}"
        if units is not None:
            return str(units)

        return None

    def _entity_normalized(self, entity):
        """Retourne une valeur normalisée quand possible."""
        if not entity:
            return None

        normalized = entity.get("normalizedValue", {})

        if normalized.get("text"):
            return normalized.get("text")

        money_value = normalized.get("moneyValue", {})
        units = money_value.get("units")
        nanos = money_value.get("nanos")

        if units is not None and nanos is not None:
            value = float(units) + (float(nanos) / 1_000_000_000)
            return round(value, 2)
        if units is not None:
            return float(units)

        return self._entity_mention(entity)

    def _get_first_entity(self, parsed, entity_type):
        """Retourne la première entité d'un type donné."""
        for entity in parsed.get("entities", []):
            if entity.get("type") == entity_type:
                return entity
        return None

    def _get_first_value(self, parsed, entity_type):
        """Retourne la valeur texte de la première entité du type."""
        entity = self._get_first_entity(parsed, entity_type)
        return self._entity_mention(entity)

    def _get_first_normalized(self, parsed, entity_type):
        """Retourne la valeur normalisée de la première entité du type."""
        entity = self._get_first_entity(parsed, entity_type)
        return self._entity_normalized(entity)

    def _build_simplified_json(self, parsed):
        """Transforme le JSON DocAI brut en JSON simplifié structuré."""

        simplified = {
            "amount_due": self._get_first_value(parsed, "amount_due"),
            "amount_paid_since_last_invoice": self._get_first_value(parsed, "amount_paid_since_last_invoice"),
            "carrier": self._get_first_value(parsed, "carrier"),
            "currency": self._get_first_value(parsed, "currency"),
            "currency_exchange_rate": self._get_first_value(parsed, "currency_exchange_rate"),
            "customer_tax_id": self._get_first_value(parsed, "customer_tax_id"),
            "delivery_date": self._get_first_value(parsed, "delivery_date"),
            "due_date": self._get_first_value(parsed, "due_date"),
            "freight_amount": self._get_first_value(parsed, "freight_amount"),
            "invoice_date": self._get_first_value(parsed, "invoice_date"),
            "invoice_id": self._get_first_value(parsed, "invoice_id"),
            "net_amount": self._get_first_value(parsed, "net_amount"),
            "payment_terms": self._get_first_value(parsed, "payment_terms"),
            "purchase_order": self._get_first_value(parsed, "purchase_order"),
            "receiver_address": self._get_first_value(parsed, "receiver_address"),
            "receiver_email": self._get_first_value(parsed, "receiver_email"),
            "receiver_name": self._get_first_value(parsed, "receiver_name"),
            "receiver_phone": self._get_first_value(parsed, "receiver_phone"),
            "receiver_tax_id": self._get_first_value(parsed, "receiver_tax_id"),
            "receiver_website": self._get_first_value(parsed, "receiver_website"),
            "remit_to_address": self._get_first_value(parsed, "remit_to_address"),
            "remit_to_name": self._get_first_value(parsed, "remit_to_name"),
            "ship_from_address": self._get_first_value(parsed, "ship_from_address"),
            "ship_from_name": self._get_first_value(parsed, "ship_from_name"),
            "ship_to_address": self._get_first_value(parsed, "ship_to_address"),
            "ship_to_name": self._get_first_value(parsed, "ship_to_name"),
            "supplier_address": self._get_first_value(parsed, "supplier_address"),
            "supplier_email": self._get_first_value(parsed, "supplier_email"),
            "supplier_iban": self._get_first_value(parsed, "supplier_iban"),
            "supplier_name": self._get_first_value(parsed, "supplier_name"),
            "supplier_payment_ref": self._get_first_value(parsed, "supplier_payment_ref"),
            "supplier_phone": self._get_first_value(parsed, "supplier_phone"),
            "supplier_registration": self._get_first_value(parsed, "supplier_registration"),
            "supplier_tax_id": self._get_first_value(parsed, "supplier_tax_id"),
            "supplier_website": self._get_first_value(parsed, "supplier_website"),
            "total_amount": self._get_first_value(parsed, "total_amount"),
            "total_tax_amount": self._get_first_value(parsed, "total_tax_amount"),
            "line_items": [],
            "vat": [],
        }

        # -----------------------------
        # Lignes de facture
        # -----------------------------
        for entity in parsed.get("entities", []):
            if entity.get("type") != "line_item":
                continue

            line = {
                "description": None,
                "amount": None,
                "product_code": None,
                "purchase_order": None,
                "quantity": None,
                "unit": None,
                "unit_price": None,
            }

            for prop in entity.get("properties", []):
                prop_type = prop.get("type")
                if prop_type in line:
                    line[prop_type] = self._entity_mention(prop)

            simplified["line_items"].append(line)

        # -----------------------------
        # TVA
        # -----------------------------
        for entity in parsed.get("entities", []):
            if entity.get("type") != "vat":
                continue

            vat_line = {
                "amount": None,
                "category_code": None,
                "tax_amount": None,
                "tax_rate": None,
            }

            for prop in entity.get("properties", []):
                prop_type = prop.get("type")
                if prop_type in vat_line:
                    vat_line[prop_type] = self._entity_mention(prop)

            simplified["vat"].append(vat_line)

        return simplified

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

            raw_document = documentai.RawDocument(
                content=pdf_content,
                mime_type="application/pdf"
            )

            process_request = documentai.ProcessRequest(
                name=f"projects/{project_id}/locations/{location}/processors/{processor_id}",
                raw_document=raw_document
            )

            result = client.process_document(request=process_request)

            raw_json = documentai.Document.to_json(result.document)
            parsed = json.loads(raw_json)

            if not parsed.get("entities"):
                _logger.warning(f"[DocAI] {label} → aucune entité détectée")
                return None, None

            minimal = self._build_simplified_json(parsed)
            return raw_json, json.dumps(minimal, indent=2, ensure_ascii=False)

        except Exception as e:
            _logger.warning(f"[DocAI] {label} → erreur lors de l’analyse : {e}")
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

        # 1. Facture
        raw_json, minimal = self._try_processor(
            pdf_content, invoice_processor, "Facture", project_id, location, key_path
        )
        if raw_json:
            return raw_json, minimal, "Facture"

        # 2. Ticket de caisse
        raw_json, minimal = self._try_processor(
            pdf_content, expense_processor, "Ticket de caisse", project_id, location, key_path
        )
        if raw_json:
            return raw_json, minimal, "Ticket de caisse"

        # 3. Autres processors à venir
        return None, None, None

    # -------------------------------------------------------------------------
    # Méthode principale : analyse DocAI
    # -------------------------------------------------------------------------
    def action_docai_analyze_attachment(self, force=False):
        for move in self:
            try:
                if (move.docai_analyzed and not force) or (move.amount_total and not force):
                    _logger.info(f"[DocAI] {move.name or move.id} ignoré (déjà analysé ou total présent)")
                    continue

                attachment = self.env["ir.attachment"].search([
                    ("res_model", "=", "account.move"),
                    ("res_id", "=", move.id),
                    ("mimetype", "=", "application/pdf")
                ], limit=1)

                if not attachment:
                    _logger.warning(f"[DocAI] Aucun PDF trouvé pour {move.name or move.id}, skip")
                    continue

                pdf_content = base64.b64decode(attachment.datas or b"")
                if not pdf_content:
                    _logger.warning(f"[DocAI] PDF vide ou illisible pour {move.name or move.id}")
                    continue

                raw_json, minimal, label = move.analyze_with_fallback(pdf_content)
                if not raw_json:
                    _logger.warning(f"[DocAI] Aucun résultat pour {move.name or move.id}")
                    continue

                vals = {}
                if not move.docai_json_raw or force:
                    vals["docai_json_raw"] = raw_json
                if not move.docai_json or force:
                    vals["docai_json"] = minimal

                if vals:
                    vals["docai_analyzed"] = True
                    move.write(vals)
                    _logger.info(f"✅ {label} {move.name or move.id} analysé et sauvegardé par DocAI")
                else:
                    _logger.info(f"ℹ️ {label} {move.name or move.id} déjà avec JSON, aucune mise à jour")

            except Exception as e:
                _logger.error(f"❌ Erreur DocAI sur {move.name or move.id} : {e}")
                continue

    # -------------------------------------------------------------------------
    # Rafraîchir (forcer réanalyse)
    # -------------------------------------------------------------------------
    def action_docai_refresh_json(self):
        return self.action_docai_analyze_attachment(force=True)

    # -------------------------------------------------------------------------
    # CRON — robuste et non bloquant
    # -------------------------------------------------------------------------
    @api.model
    def cron_docai_analyze_invoices(self):
        try:
            moves = self.env["account.move"].search([
                ("move_type", "=", "in_invoice"),
                ("state", "=", "draft"),
                ("docai_analyzed", "=", False),
                ("docai_json", "=", False),
            ], limit=10)

            _logger.info(f"[DocAI CRON] {len(moves)} documents à analyser")

            if not moves:
                return

            moves.action_docai_analyze_attachment(force=False)

        except Exception as e:
            _logger.error(f"❌ Erreur CRON DocAI : {e}")
            return False

    # -------------------------------------------------------------------------
    # Boutons de téléchargement JSON
    # -------------------------------------------------------------------------
    def action_docai_download_json_raw(self):
        """Téléchargement du JSON complet (DocAI brut)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/docai/download/{self.id}/raw",
            "target": "new",
        }

    def action_docai_download_json_min(self):
        """Téléchargement du JSON simplifié."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/docai/download/{self.id}/min",
            "target": "new",
        }


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
