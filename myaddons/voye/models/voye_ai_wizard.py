# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError

from ..services.ollama_client import OllamaClient

class VoyeAiWizard(models.TransientModel):
    _name = "voye.ai.wizard"
    _description = "Voye - Assistant IA"

    prompt = fields.Text(required=True)
    answer = fields.Text(readonly=True)
    model_name = fields.Char(readonly=True)

    def action_ask(self):
        self.ensure_one()

        prompt = (self.prompt or "").strip()
        if not prompt:
            raise UserError("Écris un prompt.")

        if len(prompt) > 4000:
            raise UserError("Prompt trop long (max 4000 caractères).")

        icp = self.env["ir.config_parameter"].sudo()
        base_url = icp.get_param("voye.ollama_base_url", "http://127.0.0.1:11434")
        model = icp.get_param("voye.ollama_model", "deepseek-r1:7b")

        system = (
            "Tu es l'assistant de Voye dans Odoo. "
            "Réponds en français, court, concret. "
            "Si info manquante, pose 1-2 questions. "
            "N'invente pas. Ne demande jamais de mots de passe/clé."
        )

        client = OllamaClient(base_url=base_url, model=model, timeout=120)
        answer = client.chat(prompt=prompt, system=system, temperature=0.2)

        self.answer = answer
        self.model_name = model
        return {
            "type": "ir.actions.act_window",
            "res_model": "voye.ai.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }
