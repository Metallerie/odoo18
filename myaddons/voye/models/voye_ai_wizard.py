# -*- coding: utf-8 -*-
import time

from odoo import models, fields
from odoo.exceptions import UserError

from ..services.ollama_client import OllamaClient


class VoyeAiWizard(models.TransientModel):
    _name = "voye.ai.wizard"
    _description = "Voye - Assistant IA"

    prompt = fields.Text(string="Prompt", required=True)
    answer = fields.Text(string="Réponse", readonly=True)
    model_name = fields.Char(string="Modèle", readonly=True)

    def _build_system_prompt(self) -> str:
        return (
            "Tu es l’assistant de la Métallerie. "
            "Ton rôle est d’aider à comprendre et relier les différentes facettes de l’entreprise : "
            "comptabilité, clients, fournisseurs et fabrication en atelier. "
            "Tu réponds en français, de façon claire, courte et concrète. "
            "Si une information manque, tu poses 1 à 2 questions. "
            "Tu n’inventes jamais de données. "
            "Tu n’utilises pas de jargon inutile. "
            "Tu ne demandes jamais de mots de passe, clés ou informations sensibles."
        )

    def _get_ollama_config(self):
        icp = self.env["ir.config_parameter"].sudo()
        base_url = icp.get_param("voye.ollama_base_url", "http://127.0.0.1:11434")
        model = icp.get_param("voye.ollama_model", "deepseek-r1:7b")
        return base_url, model

    def _validate_prompt(self, prompt: str):
        if not prompt or not prompt.strip():
            raise UserError("Écris un prompt.")
        if len(prompt) > 4000:
            raise UserError("Prompt trop long (max 4000 caractères).")

    def action_ask(self):
        self.ensure_one()

        prompt = (self.prompt or "").strip()
        self._validate_prompt(prompt)

        base_url, model = self._get_ollama_config()
        system = self._build_system_prompt()

        client = OllamaClient(
            base_url=base_url,
            model=model,
            timeout=120,
        )

        t0 = time.time()
        try:
            answer = client.chat(
                prompt=prompt,
                system=system,
                temperature=0.2,
            )
            duration_ms = int((time.time() - t0) * 1000)

            # Log structuré
            self.env["voye.ai.log"].sudo().create({
                "user_id": self.env.user.id,
                "model_name": model,
                "prompt": prompt,
                "answer": answer,
                "duration_ms": duration_ms,
                "state": "ok",
            })

            self.answer = answer
            self.model_name = model

        except Exception as e:
            duration_ms = int((time.time() - t0) * 1000)
            self.env["voye.ai.log"].sudo().create({
                "user_id": self.env.user.id,
                "model_name": model,
                "prompt": prompt,
                "answer": "",
                "duration_ms": duration_ms,
                "state": "error",
                "error_message": str(e)[:250],
            })
            raise

        return {
            "type": "ir.actions.act_window",
            "res_model": "voye.ai.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }
