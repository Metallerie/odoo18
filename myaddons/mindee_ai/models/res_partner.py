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

    # Historique versionné
    labelstudio_history_ids = fields.One2many(
        "mindee.labelstudio.history", "partner_id", string="Historique Label Studio"
    )

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


class LabelStudioHistory(models.Model):
    _name = "mindee.labelstudio.history"
    _description = "Historique Label Studio"
    _order = "version_date desc, id desc"

    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade")
    version_date = fields.Datetime("Date", default=fields.Datetime.now, required=True)
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, string="Auteur")
    json_content = fields.Text("JSON")
    xml_content = fields.Text("XML")

    def action_restore_labelstudio_version(self):
        for history in self:
            if not history.partner_id:
                continue
            if history.json_content:
                history.partner_id._validate_json(history.json_content)
            if history.xml_content:
                history.partner_id._validate_xml(history.xml_content)
            history.partner_id.write({
                "labelstudio_json": history.json_content or "",
                "labelstudio_xml": history.xml_content or "",
            })

    def action_download_json(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/mindee/labelstudio/download/json/{self.id}",
            "target": "self",
        }

    def action_download_xml(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/mindee/labelstudio/download/xml/{self.id}",
            "target": "self",
        }
