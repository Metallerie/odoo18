import base64
import json
import logging
import subprocess
from datetime import datetime, date
from odoo import models, fields
from odoo.exceptions import UserError

# Mets le logger du module en DEBUG avec --log-handler=odoo.addons.mindee_ai:DEBUG
_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    mindee_local_response = fields.Text(
        string="Réponse OCR JSON (Tesseract)",
        readonly=True,
        store=True,
    )

    # ---------------- Utils ----------------

    def _normalize_date(self, date_str):
        if not date_str:
            return None
        s = str(date_str).strip().replace("-", "/").replace(".", "/")
        for fmt in ("%d/%m/%Y", "%Y/%m/%d", "%d/%m/%y", "%d/%m/%y", "%d/%m/%y"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                continue
        # essais supplémentaires fréquents
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(str(date_str), fmt).date()
            except Exception:
                continue
        return None

    def _first_parsed_values(self, ocr_data):
        """Récupère le 1er invoice_number / invoice_date trouvés sur l’ensemble des pages."""
        out = {}
        for page in (ocr_data or {}).get("pages", []):
            p = page.get("parsed", {}) or {}
            if "invoice_number" not in out and p.get("invoice_number"):
                out["invoice_number"] = p.get("invoice_number")
            if "invoice_date" not in out and p.get("invoice_date"):
                out["invoice_date"] = p.get("invoice_date")
            if len(out) == 2:
                break
        return out

    def _apply_ocr_rules(self, vals, ocr_data, parsed):
        """Applique ocr.configuration.rule pour remplir partner_id (text/number/date sans total_amount)."""
        Rule = self.env["ocr.configuration.rule"]
        rules = Rule.search([("active", "=", True)], order="sequence")

        # Construire les valeurs disponibles
        phrases_all_pages = []
        for p in (ocr_data or {}).get("pages", []):
            phrases_all_pages.extend(p.get("phrases", []) or [])
        raw_text = " ".join(phrases_all_pages)

        invoice_number = (parsed or {}).get("invoice_number", "") or ""
        partner_name_ocr = (parsed or {}).get("supplier_name", "") or ""  # peut être vide (fallback raw_text)
        invoice_date_str = (parsed or {}).get("invoice_date", "") or ""

        _logger.debug("[OCR][RULES] raw_text_len=%s, inv_num=%s, inv_date=%s, partner_name_ocr=%s",
                      len(raw_text), invoice_number, invoice_date_str, partner_name_ocr)

        def text_match(value: str, rule) -> bool:
            if not value or not rule.value_text:
                return False
            val = value.lower().strip()
            cmpv = rule.value_text.lower().strip()
            if rule.operator == "contains":
                return cmpv in val
            if rule.operator == "==":
                return val == cmpv
            if rule.operator == "startswith":
                return val.startswith(cmpv)
            if rule.operator == "endswith":
                return val.endswith(cmpv)
            return False

        def date_match(value_str: str, rule) -> bool:
            # value_str (OCR) -> date ; rule.value_date -> date
            if not value_str or not rule.value_date:
                return False
            v = self._normalize_date(value_str)
            if not isinstance(v, (date, datetime)):
                return False
            v = v if isinstance(v, date) else v.date()
            r = rule.value_date
            if rule.operator == "==":
                return v == r
            if rule.operator == ">=":
                return v >= r
            if rule.operator == "<=":
                return v <= r
            if rule.operator == ">":
                return v > r
            if rule.operator == "<":
                return v < r
            return False

        for rule in rules:
            value_for_rule = None
            if rule.variable == "partner_name":
                value_for_rule = partner_name_ocr or raw_text   # fallback
            elif rule.variable == "invoice_number":
                value_for_rule = invoice_number
            elif rule.variable == "invoice_date":
                value_for_rule = invoice_date_str
            else:
                # on ignore total_amount etc. pour l’instant
                continue

            matched = False
            if rule.condition_type == "text":
                matched = text_match(value_for_rule, rule)
            elif rule.condition_type == "date":
                matched = date_match(value_for_rule, rule)

            _logger.debug(
                "[OCR][RULES] test rule(id=%s, seq=%s, name=%s, var=%s, type=%s, op=%s, "
                "value_text=%s, value_date=%s) on='%s' -> matched=%s",
                rule.id, rule.sequence, rule.name, rule.variable, rule.condition_type,
                rule.operator, rule.value_text, rule.value_date, str(value_for_rule)[:200], matched
            )

            if matched and rule.partner_id:
                vals["partner_id"] = rule.partner_id.id
                _logger.info("[OCR][RULES] MATCH rule '%s' -> partner set to '%s' (id=%s)",
                             rule.name, rule.partner_id.name, rule.partner_id.id)
                break  # stop au premier match

        return vals

    # ---------------- Action ----------------

    def action_ocr_fetch(self):
        for move in self:
            _logger.info("[OCR] Start for move id=%s name=%s", move.id, move.name)

            # 1) Récup PDF
            pdf_attachments = move.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf")[:1]
            if not pdf_attachments:
                raise UserError("Aucune pièce jointe PDF trouvée sur cette facture.")
            attachment = pdf_attachments[0]
            _logger.debug("[OCR] Attachment found: id=%s name=%s", attachment.id, attachment.name)

            file_path = "/tmp/ocr_temp_file.pdf"
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(attachment.datas))

            # 2) Run OCR
            venv_python = "/data/odoo/odoo18-venv/bin/python3"
            tesseract_script_path = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/scripts/tesseract_runner.py"

            try:
                result = subprocess.run(
                    [venv_python, tesseract_script_path, file_path],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=180, check=True, encoding="utf-8",
                )
                ocr_json = result.stdout.strip()
                _logger.debug("[OCR] Script OK. stdout(len)=%s, stderr(len)=%s",
                              len(result.stdout or ""), len(result.stderr or ""))
                # log un extrait (éviter les logs géants)
                _logger.debug("[OCR] stdout head: %s", (ocr_json[:500] + '...') if len(ocr_json) > 500 else ocr_json)
                ocr_data = json.loads(ocr_json)
            except subprocess.CalledProcessError as e:
                _logger.error("[OCR] Script ERROR for %s. STDERR: %s", attachment.name, e.stderr)
                raise UserError(f"Erreur OCR :\n\nSTDERR:\n{e.stderr}\n\nSTDOUT:\n{e.stdout}")
            except Exception as e:
                _logger.exception("[OCR] Unexpected error")
                raise UserError(f"Erreur OCR avec Tesseract : {e}")

            # 3) Sauvegarde JSON
            move.mindee_local_response = json.dumps(ocr_data, indent=2, ensure_ascii=False)
            self.env["ir.attachment"].create({
                "name": f"OCR_{attachment.name}.json",
                "res_model": "account.move",
                "res_id": move.id,
                "type": "binary",
                "mimetype": "application/json",
                "datas": base64.b64encode(json.dumps(ocr_data, indent=2).encode("utf-8")),
            })
            _logger.debug("[OCR] JSON saved as attachment")

            # 4) Lecture parsed (toutes pages)
            parsed = self._first_parsed_values(ocr_data)
            _logger.debug("[OCR] parsed=%s", parsed)

            vals = {}
            if parsed.get("invoice_date"):
                vals["invoice_date"] = self._normalize_date(parsed["invoice_date"])
            if parsed.get("invoice_number"):
                vals["ref"] = parsed["invoice_number"]
            _logger.debug("[OCR] base vals=%s", vals)

            # 5) Règles OCR
            vals = self._apply_ocr_rules(vals, ocr_data, parsed)
            _logger.debug("[OCR] vals after rules=%s", vals)

            # 6) Write
            if vals:
                try:
                    move.write(vals)
                    _logger.info("[OCR] move %s updated: %s", move.id, vals)
                except Exception as e:
                    _logger.exception("[OCR] Write error on move %s", move.id)
                    raise UserError(f"Erreur d’écriture dans la facture : {e}")

        return True
