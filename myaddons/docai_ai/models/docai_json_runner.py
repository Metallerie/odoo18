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
    docai_json = fields.Text("JSON formaté DocAI", readonly=True)
    docai_analyzed = fields.Boolean("Analysée par DocAI", default=False, readonly=True)

    # -------------------------------------------------------------------------
    # OUTILS
    # -------------------------------------------------------------------------
    def _docai_entity_to_field_value(self, entity):
        """
        Retourne la valeur brute la plus directe possible d'une entité DocAI,
        sans normalisation ni interprétation.
        Priorité :
        - mentionText
        - normalizedValue.text
        - normalizedValue.moneyValue
        - normalizedValue.floatValue
        - normalizedValue.integerValue
        """
        if not entity:
            return None

        mention = entity.get("mentionText")
        if mention not in (None, ""):
            return mention

        normalized = entity.get("normalizedValue", {}) or {}

        if normalized.get("text") not in (None, ""):
            return normalized.get("text")

        money_value = normalized.get("moneyValue", {}) or {}
        units = money_value.get("units")
        nanos = money_value.get("nanos")

        if units is not None and nanos is not None:
            return {
                "units": units,
                "nanos": nanos,
                "currencyCode": money_value.get("currencyCode"),
            }

        if units is not None:
            return {
                "units": units,
                "currencyCode": money_value.get("currencyCode"),
            }

        if normalized.get("floatValue") is not None:
            return normalized.get("floatValue")

        if normalized.get("integerValue") is not None:
            return normalized.get("integerValue")

        return None

    def _docai_format_properties(self, props):
        """
        Transforme les properties d'une entité en dict lisible.
        Exemple :
        line_item/product_code -> product_code
        line_item/description  -> description
        vat/tax_rate           -> tax_rate
        """
        result = {}

        for prop in props or []:
            prop_type = prop.get("type") or ""
            key = prop_type.split("/")[-1] if "/" in prop_type else prop_type
            value = self._docai_entity_to_field_value(prop)

            if key in result:
                if not isinstance(result[key], list):
                    result[key] = [result[key]]
                result[key].append(value)
            else:
                result[key] = value

        return result

    def _build_formatted_json(self, parsed):
        """
        Version formatée en fields, sans traitement métier.
        On garde :
        - les entités simples en champs
        - les line_item en tableau d'objets
        - les vat en tableau d'objets
        """
        result = {}
        line_items = []
        vat_items = []

        for entity in parsed.get("entities", []):
            entity_type = entity.get("type")
            props = entity.get("properties", []) or []

            # Cas line_item
            if entity_type == "line_item":
                item = self._docai_format_properties(props)

                # on garde aussi la ligne brute si utile
                item["_mentionText"] = entity.get("mentionText")
                line_items.append(item)
                continue

            # Cas vat
            if entity_type == "vat":
                vat = self._docai_format_properties(props)
                vat["_mentionText"] = entity.get("mentionText")
                vat_items.append(vat)
                continue

            # Cas entité simple
            value = self._docai_entity_to_field_value(entity)

            if entity_type in result:
                if not isinstance(result[entity_type], list):
                    result[entity_type] = [result[entity_type]]
                result[entity_type].append(value)
            else:
                result[entity_type] = value

        result["line_items"] = line_items
        result["vat"] = vat_items

        return result

    # -------------------------------------------------------------------------
    # ESSAI AVEC UN PROCESSOR DONNE
    # -------------------------------------------------------------------------
    def _try_processor(self, pdf_content, processor_id, label, project_id, location, key_path):
        """Tente une analyse avec un processor spécifique."""
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

            formatted = self._build_formatted_json(parsed)

            return raw_json, json.dumps(formatted, indent=2, ensure_ascii=False)

        except Exception as e:
            _logger.warning(f"[DocAI] {label} → erreur lors de l’analyse : {e}")
            return None, None

    # -------------------------------------------------------------------------
    # CASCADE D'ANALYSE
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
        raw_json, formatted = self._try_processor(
            pdf_content=pdf_content,
            processor_id=invoice_processor,
            label="Facture",
            project_id=project_id,
            location=location,
            key_path=key_path,
        )
        if raw_json:
            return raw_json, formatted, "Facture"

        # 2. Ticket de caisse
        raw_json, formatted = self._try_processor(
            pdf_content=pdf_content,
            processor_id=expense_processor,
            label="Ticket de caisse",
            project_id=project_id,
            location=location,
            key_path=key_path,
        )
        if raw_json:
            return raw_json, formatted, "Ticket de caisse"

        return None, None, None

    # -------------------------------------------------------------------------
    # METHODE PRINCIPALE
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

                raw_json, formatted, label = move.analyze_with_fallback(pdf_content)
                if not raw_json:
                    _logger.warning(f"[DocAI] Aucun résultat pour {move.name or move.id}")
                    continue

                vals = {"docai_analyzed": True}

                if not move.docai_json_raw or force:
                    vals["docai_json_raw"] = raw_json

                if not move.docai_json or force:
                    vals["docai_json"] = formatted

                move.write(vals)
                _logger.info(f"✅ {label} {move.name or move.id} analysé et sauvegardé par DocAI")

            except Exception as e:
                _logger.error(f"❌ Erreur DocAI sur {move.name or move.id} : {e}")
                continue

    # -------------------------------------------------------------------------
    # RAFRAICHIR
    # -------------------------------------------------------------------------
    def action_docai_refresh_json(self):
        return self.action_docai_analyze_attachment(force=True)

    # -------------------------------------------------------------------------
    # CRON
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
                return True

            moves.action_docai_analyze_attachment(force=False)
            return True

        except Exception as e:
            _logger.error(f"❌ Erreur CRON DocAI : {e}")
            return False

    # -------------------------------------------------------------------------
    # TELECHARGEMENT JSON
    # -------------------------------------------------------------------------
    def action_docai_download_json_raw(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/docai/download/{self.id}/raw",
            "target": "new",
        }

    def action_docai_download_json_min(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/docai/download/{self.id}/min",
            "target": "new",
        }


class DocaiDownloadController(http.Controller):

    @http.route('/docai/download/<int:move_id>/<string:kind>', type='http', auth='user')
    def download_json(self, move_id, kind="min", **kwargs):
        move = request.env["account.move"].browse(move_id)
        if not move.exists():
            return request.not_found()

        content = move.docai_json_raw if kind == "raw" else move.docai_json
        if not content:
            return request.not_found()

        filename = f"document_{move.id}_{kind}.json"
        return request.make_response(
            content,
            headers=[
                ("Content-Type", "application/json"),
                ("Content-Disposition", f'attachment; filename="{filename}"'),
            ],
        )
