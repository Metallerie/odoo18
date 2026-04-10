# -*- coding: utf-8 -*-
# docai_json_runner.py

import base64
import os
import json
import logging
import re
from datetime import datetime

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
    # OUTILS
    # -------------------------------------------------------------------------
    def _docai_clean_text(self, value):
        """Nettoie les valeurs vides / parasites."""
        if value in (None, "", False):
            return None
        if isinstance(value, str):
            value = value.strip()
            if value in ("--", "-", "N/A", "n/a"):
                return None
        return value

    def _docai_entity_value(self, entity):
        """Retourne la meilleure valeur texte possible d'une entité DocAI."""
        if not entity:
            return None

        mention = self._docai_clean_text(entity.get("mentionText"))
        if mention is not None:
            return mention

        normalized = entity.get("normalizedValue", {}) or {}

        text_value = self._docai_clean_text(normalized.get("text"))
        if text_value is not None:
            return text_value

        money_value = normalized.get("moneyValue", {}) or {}
        units = money_value.get("units")
        nanos = money_value.get("nanos")

        if units is not None:
            nanos = nanos or 0
            value = float(units) + (float(nanos) / 1_000_000_000)
            return str(round(value, 6)).rstrip("0").rstrip(".")

        float_value = normalized.get("floatValue")
        if float_value is not None:
            return str(float_value)

        int_value = normalized.get("integerValue")
        if int_value is not None:
            return str(int_value)

        return None

    def _docai_find_first(self, parsed, entity_type):
        """Retourne la première entité du type demandé."""
        for entity in parsed.get("entities", []):
            if entity.get("type") == entity_type:
                return entity
        return None

    def _docai_first_value(self, parsed, entity_type):
        """Retourne la valeur de la première entité du type demandé."""
        return self._docai_entity_value(self._docai_find_first(parsed, entity_type))

    def _docai_get_prop_value(self, props, prop_type):
        """Retourne la valeur d'une propriété de line_item / vat."""
        for prop in props:
            if prop.get("type") == prop_type:
                return self._docai_entity_value(prop)
        return None

    def _docai_normalize_amount(self, value):
        """Normalise un montant texte en chaîne décimale simple."""
        value = self._docai_clean_text(value)
        if value is None:
            return None

        if not isinstance(value, str):
            return str(value)

        cleaned = value.strip()

        # Supprime symboles monétaires et textes annexes
        cleaned = cleaned.replace("€", "")
        cleaned = cleaned.replace("EUR", "")
        cleaned = cleaned.replace("eur", "")
        cleaned = cleaned.strip()

        # Garde uniquement chiffres / séparateurs / signe
        cleaned = re.sub(r"[^0-9,.\-]", "", cleaned)

        if not cleaned:
            return None

        # Cas FR : 1.234,56
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")

        # Cas FR : 123,45
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")

        try:
            num = float(cleaned)
            return f"{num:.6f}".rstrip("0").rstrip(".")
        except Exception:
            return value

    def _docai_normalize_date(self, value):
        """Normalise une date en YYYY-MM-DD."""
        value = self._docai_clean_text(value)
        if value is None:
            return None

        if not isinstance(value, str):
            return str(value)

        raw = value.strip()

        # Déjà normalisée
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        # Formats courants
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        # Cas DocAI du style 2026-2-10
        match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", raw)
        if match:
            y, m, d = match.groups()
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

        return value

    def _docai_normalize_percent(self, value):
        """Normalise un taux style 20% -> 20."""
        value = self._docai_clean_text(value)
        if value is None:
            return None

        if not isinstance(value, str):
            return str(value)

        cleaned = value.replace("%", "").strip()
        cleaned = cleaned.replace(",", ".")
        try:
            num = float(cleaned)
            return f"{num:.6f}".rstrip("0").rstrip(".")
        except Exception:
            return value

    def _docai_postprocess_simplified_json(self, simplified):
        """Normalise les champs du JSON simplifié."""

        amount_fields = [
            "amount_due",
            "amount_paid_since_last_invoice",
            "currency_exchange_rate",
            "freight_amount",
            "net_amount",
            "total_amount",
            "total_tax_amount",
        ]

        date_fields = [
            "delivery_date",
            "due_date",
            "invoice_date",
        ]

        for field_name in amount_fields:
            simplified[field_name] = self._docai_normalize_amount(simplified.get(field_name))

        for field_name in date_fields:
            simplified[field_name] = self._docai_normalize_date(simplified.get(field_name))

        for line in simplified.get("line_items", []):
            line["amount"] = self._docai_normalize_amount(line.get("amount"))
            line["quantity"] = self._docai_normalize_amount(line.get("quantity"))
            line["unit_price"] = self._docai_normalize_amount(line.get("unit_price"))

        for vat_line in simplified.get("vat", []):
            vat_line["amount"] = self._docai_normalize_amount(vat_line.get("amount"))
            vat_line["tax_amount"] = self._docai_normalize_amount(vat_line.get("tax_amount"))
            vat_line["tax_rate"] = self._docai_normalize_percent(vat_line.get("tax_rate"))

        return simplified

    # -------------------------------------------------------------------------
    # JSON SIMPLIFIÉ
    # -------------------------------------------------------------------------
    def _build_simplified_json(self, parsed):
        """Transforme le JSON DocAI brut en JSON simplifié structuré."""

        simplified = {
            "amount_due": self._docai_first_value(parsed, "amount_due"),
            "amount_paid_since_last_invoice": self._docai_first_value(parsed, "amount_paid_since_last_invoice"),
            "carrier": self._docai_first_value(parsed, "carrier"),
            "currency": self._docai_first_value(parsed, "currency"),
            "currency_exchange_rate": self._docai_first_value(parsed, "currency_exchange_rate"),
            "customer_tax_id": self._docai_first_value(parsed, "customer_tax_id"),
            "delivery_date": self._docai_first_value(parsed, "delivery_date"),
            "due_date": self._docai_first_value(parsed, "due_date"),
            "freight_amount": self._docai_first_value(parsed, "freight_amount"),
            "invoice_date": self._docai_first_value(parsed, "invoice_date"),
            "invoice_id": self._docai_first_value(parsed, "invoice_id"),
            "net_amount": self._docai_first_value(parsed, "net_amount"),
            "payment_terms": self._docai_first_value(parsed, "payment_terms"),
            "purchase_order": self._docai_first_value(parsed, "purchase_order"),
            "receiver_address": self._docai_first_value(parsed, "receiver_address"),
            "receiver_email": self._docai_first_value(parsed, "receiver_email"),
            "receiver_name": self._docai_first_value(parsed, "receiver_name"),
            "receiver_phone": self._docai_first_value(parsed, "receiver_phone"),
            "receiver_tax_id": self._docai_first_value(parsed, "receiver_tax_id"),
            "receiver_website": self._docai_first_value(parsed, "receiver_website"),
            "remit_to_address": self._docai_first_value(parsed, "remit_to_address"),
            "remit_to_name": self._docai_first_value(parsed, "remit_to_name"),
            "ship_from_address": self._docai_first_value(parsed, "ship_from_address"),
            "ship_from_name": self._docai_first_value(parsed, "ship_from_name"),
            "ship_to_address": self._docai_first_value(parsed, "ship_to_address"),
            "ship_to_name": self._docai_first_value(parsed, "ship_to_name"),
            "supplier_address": self._docai_first_value(parsed, "supplier_address"),
            "supplier_email": self._docai_first_value(parsed, "supplier_email"),
            "supplier_iban": self._docai_first_value(parsed, "supplier_iban"),
            "supplier_name": self._docai_first_value(parsed, "supplier_name"),
            "supplier_payment_ref": self._docai_first_value(parsed, "supplier_payment_ref"),
            "supplier_phone": self._docai_first_value(parsed, "supplier_phone"),
            "supplier_registration": self._docai_first_value(parsed, "supplier_registration"),
            "supplier_tax_id": self._docai_first_value(parsed, "supplier_tax_id"),
            "supplier_website": self._docai_first_value(parsed, "supplier_website"),
            "total_amount": self._docai_first_value(parsed, "total_amount"),
            "total_tax_amount": self._docai_first_value(parsed, "total_tax_amount"),
            "line_items": [],
            "vat": [],
        }

        # -----------------------------
        # Lignes de facture
        # -----------------------------
        for entity in parsed.get("entities", []):
            if entity.get("type") != "line_item":
                continue

            props = entity.get("properties", []) or []

            line = {
                "description": self._docai_get_prop_value(props, "description"),
                "amount": self._docai_get_prop_value(props, "amount"),
                "product_code": self._docai_get_prop_value(props, "product_code"),
                "purchase_order": self._docai_get_prop_value(props, "purchase_order"),
                "quantity": self._docai_get_prop_value(props, "quantity"),
                "unit": self._docai_get_prop_value(props, "unit"),
                "unit_price": self._docai_get_prop_value(props, "unit_price"),
            }

            # Si la ligne n'a aucune donnée exploitable, on la saute
            if any(v not in (None, "", "--") for v in line.values()):
                simplified["line_items"].append(line)

        # -----------------------------
        # TVA
        # -----------------------------
        for entity in parsed.get("entities", []):
            if entity.get("type") != "vat":
                continue

            props = entity.get("properties", []) or []

            vat_line = {
                "amount": self._docai_get_prop_value(props, "amount"),
                "category_code": self._docai_get_prop_value(props, "category_code"),
                "tax_amount": self._docai_get_prop_value(props, "tax_amount"),
                "tax_rate": self._docai_get_prop_value(props, "tax_rate"),
            }

            if any(v not in (None, "", "--") for v in vat_line.values()):
                simplified["vat"].append(vat_line)

        simplified = self._docai_postprocess_simplified_json(simplified)
        return simplified

    # -------------------------------------------------------------------------
    # Essai avec un processor donné
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
            pdf_content=pdf_content,
            processor_id=invoice_processor,
            label="Facture",
            project_id=project_id,
            location=location,
            key_path=key_path,
        )
        if raw_json:
            return raw_json, minimal, "Facture"

        # 2. Ticket de caisse
        raw_json, minimal = self._try_processor(
            pdf_content=pdf_content,
            processor_id=expense_processor,
            label="Ticket de caisse",
            project_id=project_id,
            location=location,
            key_path=key_path,
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

                vals = {"docai_analyzed": True}

                if not move.docai_json_raw or force:
                    vals["docai_json_raw"] = raw_json

                if not move.docai_json or force:
                    vals["docai_json"] = minimal

                move.write(vals)
                _logger.info(f"✅ {label} {move.name or move.id} analysé et sauvegardé par DocAI")

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
                return True

            moves.action_docai_analyze_attachment(force=False)
            return True

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
