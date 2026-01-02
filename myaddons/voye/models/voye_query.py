# -*- coding: utf-8 -*-
import json
import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

class VoyeQuery(models.Model):
    _name = "voye.query"
    _description = "Voye Query"
    _order = "create_date desc"

    question = fields.Text(required=True)
    answer = fields.Text(readonly=True)
    answer_json = fields.Text(readonly=True)
    state = fields.Selection(
        [("draft","Brouillon"),("done","OK"),("error","Erreur")],
        default="draft",
        readonly=True
    )

    def action_ask_voye(self):
        self.ensure_one()
        # URL Voye (tu pourras le mettre en param système après)
        voye_url = self.env["ir.config_parameter"].sudo().get_param(
            "voye.api_url", "http://127.0.0.1:1999"
        )

        payload = {
            "question": self.question,
            "context": {
                "db": self.env.cr.dbname,
                "company_id": self.env.company.id,
                "user_id": self.env.user.id,
            }
        }

        try:
            r = requests.post(f"{voye_url}/ask", json=payload, timeout=20)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            self.write({"state": "error", "answer": str(e)})
            raise UserError(f"Voye indisponible: {e}")

        self.write({
            "state": "done",
            "answer": data.get("answer", ""),
            "answer_json": json.dumps(data, ensure_ascii=False, indent=2),
        })
