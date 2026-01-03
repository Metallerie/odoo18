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

    # Lien vers l'historique créé pour cette question
    log_id = fields.Many2one("voye.ai.log", string="Historique", readonly=True)

    # Pouces dans le wizard (écrits dans le log)
    rating = fields.Selection(
        [("up", "👍 Utile"), ("down", "👎 Inutile")],
        string="Appréciation",
    )
    rating_comment = fields.Text(string="Commentaire")

    def _get_ollama_config(self):
        icp = self.env["ir.config_parameter"].sudo()
        base_url = icp.get_param("voye.ollama_base_url", "http://127.0.0.1:11434")
        model = icp.get_param("voye.ollama_model", "deepseek-r1:7b")
        return base_url, model

    def _build_system_prompt(self) -> str:
        icp = self.env["ir.config_parameter"].sudo()
        sp = icp.get_param("voye.ai_system_prompt")
        if sp and sp.strip():
            return sp.strip()

        return (
            "Tu es l’assistant interne de la Métallerie de Franck. "
            "Tu n'es pas un assistant générique et tu ne cites jamais d'autre entreprise ou marque. "
            "Ton rôle est d’aider à comprendre et relier comptabilité, clients, fournisseurs et atelier. "
            "Réponses courtes, concrètes, en français. "
            "Si une information manque, tu poses 1 à 2 questions. "
            "Tu n’inventes jamais de faits, noms, chiffres ou historiques. "
            "Si on te demande 'que sais-tu de la Métallerie' sans faits fournis, "
            "tu dis que tu n'as pas d'informations factuelles et tu demandes une courte description. "
            "Ne demande jamais de mots de passe, clés ou informations sensibles."
        )

    def _validate_prompt(self, prompt: str):
        if not prompt or not prompt.strip():
            raise UserError("Écris un prompt.")
        if len(prompt) > 4000:
            raise UserError("Prompt trop long (max 4000 caractères).")

    def _sync_rating_to_log(self):
        """Recopie rating / rating_comment du wizard vers le log."""
        self.ensure_one()
        if not self.log_id:
            return
        # Écriture autorisée par voye.ai.log.write (seulement ces champs)
        self.log_id.write({
            "rating": self.rating or False,
            "rating_comment": (self.rating_comment or "").strip() or False,
        })

    def write(self, vals):
        res = super().write(vals)
        # Si l'utilisateur change l'appréciation/commentaire dans le wizard, on synchronise
        if any(k in vals for k in ("rating", "rating_comment")):
            for wiz in self:
                wiz._sync_rating_to_log()
        return res

    def action_ask(self):
        self.ensure_one()

        prompt = (self.prompt or "").strip()
        self._validate_prompt(prompt)

        base_url, model = self._get_ollama_config()
        system = self._build_system_prompt()

        client = OllamaClient(base_url=base_url, model=model, timeout=120)

        t0 = time.time()
        try:
            answer = client.chat(prompt=prompt, system=system, temperature=0.2)
            duration_ms = int((time.time() - t0) * 1000)

            log = self.env["voye.ai.log"].sudo().create({
                "user_id": self.env.user.id,
                "model_name": model,
                "prompt": prompt,
                "answer": answer,
                "duration_ms": duration_ms,
                "state": "ok",
            })

            self.answer = answer
            self.model_name = model
            self.log_id = log.id

            # reset des pouces pour la nouvelle réponse
            self.rating = False
            self.rating_comment = False

        except Exception as e:
            duration_ms = int((time.time() - t0) * 1000)

            log = self.env["voye.ai.log"].sudo().create({
                "user_id": self.env.user.id,
                "model_name": model,
                "prompt": prompt,
                "answer": "",
                "duration_ms": duration_ms,
                "state": "error",
                "error_message": str(e)[:250],
            })

            self.model_name = model
            self.log_id = log.id
            raise

        return {
            "type": "ir.actions.act_window",
            "res_model": "voye.ai.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }
