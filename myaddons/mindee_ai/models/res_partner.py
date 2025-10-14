import base64
import json
import xml.etree.ElementTree as ET

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Dernière version "active"
    labelstudio_json = fields.Text("Label Studio JSON", help="Dernière version JSON")
    labelstudio_xml = fields.Text("Label Studio XML", help="Dernière version XML")

    # Upload fichiers → on parse et on remplit ci-dessus
    labelstudio_json_file = fields.Binary("Importer JSON")
    labelstudio_json_filename = fields.Char("Nom du fichier JSON")
    labelstudio_xml_file = fields.Binary("Importer XML")
    labelstudio_xml_filename = fields.Char("Nom du fichier XML")

    # Historique versionné
    labelstudio_history_ids = fields.One2many(
        "mindee.labelstudio.history", "partner_id", string="Historique Label Studio"
    )

    # ---------- Validation & Parsing ----------
    @staticmethod
    def _b64_to_text(b64_content: bytes) -> str:
        try:
            raw = base64.b64decode(b64_content or b"")
        except Exception:
            raise ValidationError(_("Le fichier est corrompu ou non lisible (base64)."))
        try:
            # On force utf-8, Label Studio sort en UTF-8
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
        """Si un fichier binaire est fourni, on le parse,
        on valide le contenu et on remplit labelstudio_json/xml."""
        out = dict(vals)

        # JSON
        if vals.get("labelstudio_json_file"):
            txt = self._b64_to_text(vals["labelstudio_json_file"])
            self._validate_json(txt)
            out["labelstudio_json"] = txt  # remplit le champ texte
            # on nettoie le binaire pour éviter de stocker deux fois
            out["labelstudio_json_file"] = False

        # XML
        if vals.get("labelstudio_xml_file"):
            txt = self._b64_to_text(vals["labelstudio_xml_file"])
            self._validate_xml(txt)
            out["labelstudio_xml"] = txt
            out["labelstudio_xml_file"] = False

        # Si l’utilisateur colle du texte direct, on valide aussi
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

    # ---------- Versionning ----------
    def action_save_labelstudio_version(self):
        for partner in self:
            self.env["mindee.labelstudio.history"].create({
                "partner_id": partner.id,
                "json_content": partner.labelstudio_json or "",
                "xml_content": partner.labelstudio_xml or "",
            })

    def action_restore_labelstudio_version(self):
        """Restaure depuis une version historique sélectionnée en vue form (context active_id)."""
        self.ensure_one()
        history = None
        if self.env.context.get("labelstudio_history_id"):
            history = self.env["mindee.labelstudio.history"].browse(
                self.env.context["labelstudio_history_id"]
            )
        if not history or history.partner_id.id != self.id:
            raise ValidationError(_("Aucune version valide sélectionnée."))
        # On valide avant d’écraser
        if history.json_content:
            self._validate_json(history.json_content)
        if history.xml_content:
            self._validate_xml(history.xml_content)
        self.write({
            "labelstudio_json": history.json_content or "",
            "labelstudio_xml": history.xml_content or "",
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

    def name_get(self):
        res = []
        for rec in self:
            label = f"{rec.version_date} - {rec.user_id.name or '—'}"
            res.append((rec.id, label))
        return res
