from odoo import fields, models


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

            # 🔥 D'abord on efface les anciens contenus
            history.partner_id.write({
                "labelstudio_json": False,
                "labelstudio_xml": False,
            })

            # ✅ Ensuite on restaure cette version
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
