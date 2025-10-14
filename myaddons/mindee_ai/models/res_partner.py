from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import base64
import json
import xml.etree.ElementTree as ET


class ResPartner(models.Model):
    _inherit = "res.partner"

    labelstudio_json = fields.Text("Label Studio JSON", help="Dernière version JSON")
    labelstudio_xml = fields.Text("Label Studio XML", help="Dernière version XML")

    labelstudio_json_file = fields.Binary("Importer JSON")
    labelstudio_json_filename = fields.Char("Nom du fichier JSON")
    labelstudio_xml_file = fields.Binary("Importer XML")
    labelstudio_xml_filename = fields.Char("Nom du fichier XML")

    labelstudio_history_ids = fields.One2many(
        "mindee.labelstudio.history", "partner_id", string="Historique Label Studio"
    )

    # ----------------- Validation -----------------
    @staticmethod
    def _b64_to_text(b64_content: bytes) -> str:
        raw = base64.b64decode(b64_content or b"")
        return raw.decode("utf-8")

    @staticmethod
    def _validate_json(text: str):
        json.loads(text)

    @staticmethod
    def _validate_xml(text: str):
        ET.fromstring(text)

    def _apply_uploaded_files_to_fields(self, vals: dict) -> dict:
        out = dict(vals)

        if vals.get("labelstudio_json_file"):
            txt = self._b64_to_text(vals["labelstudio_json_file"])
            self._validate_json(txt)
            out["labelstudio_json"] = txt
            out["labelstudio_json_file"] = False

        if vals.get("labelstudio_xml_file"):
            txt = self._b64_to_text(vals["labelstudio_xml_file"])
            self._validate_xml(txt)
            out["labelstudio_xml"] = txt
            out["labelstudio_xml_file"] = False

        if "labelstudio_json" in vals and vals["labelstudio_json"]:
            self._validate_json(vals["labelstudio_json"])
        if "labelstudio_xml" in vals and vals["labelstudio_xml"]:
            self._validate_xml(vals["labelstudio_xml"])

        return out

    @api.model
    def create(self, vals):
        vals = self._apply_uploaded_files_to_fields(vals)
        return super().create(vals)

    def write(self, vals):
        vals = self._apply_uploaded_files_to_fields(vals)
        return super().write(vals)

    def action_save_labelstudio_version(self):
        for partner in self:
            self.env["mindee.labelstudio.history"].create({
                "partner_id": partner.id,
                "json_content": partner.labelstudio_json or "",
                "xml_content": partner.labelstudio_xml or "",
            })
