import base64
import json
import xml.etree.ElementTree as ET

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Champs JSON/XML actifs
    labelstudio_json = fields.Text("Label Studio JSON", help="Dernière version JSON")
    labelstudio_xml = fields.Text("Label Studio XML", help="Dernière version XML")

    # Fichiers uploadés
    labelstudio_json_file = fields.Binary("Importer JSON")
    labelstudio_json_filename = fields.Char("Nom du fichier JSON")
    labelstudio_xml_file = fields.Binary("Importer XML")
    labelstudio_xml_filename = fields.Char("Nom du fichier XML")

    # ---------- Validation ----------
    @staticmethod
    def _b64_to_text(b64_content: bytes) -> str:
        try:
            raw = base64.b64decode(b64_content or b"")
        except Exception:
            raise ValidationError(_("Le fichier est corrompu ou non lisible (base64)."))
        try:
            return raw.decode("utf-8")
        except Exception:
            raise ValidationError(_("Encodage invalide : le fichier doit être en UTF-8."))

    @staticmethod
    def _validate_json(text: str):
        try:
            json.loads(text)
        except Exception as e:
            raise ValidationError(_("JSON invalide : %s") % e)

    @staticmethod
    def _validate_xml(text: str):
        try:
            ET.fromstring(text)
        except Exception as e:
            raise ValidationError(_("XML invalide : %s") % e)

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.update(self._apply_uploaded_files_to_fields(vals))
        return super().create(vals_list)

    def write(self, vals):
        vals = self._apply_uploaded_files_to_fields(vals)
        return super().write(vals)
