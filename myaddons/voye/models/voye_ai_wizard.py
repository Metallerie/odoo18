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

    # Affichage cartographie
    speaker_label = fields.Char(string="Interlocuteur", readonly=True)
    context_label = fields.Char(string="Contexte", readonly=True)
    context_ref = fields.Char(string="Réf contexte", readonly=True)

    # Lien historique
    log_id = fields.Many2one("voye.ai.log", string="Historique", readonly=True)

    # Pouces dans le wizard (synchronisés vers le log)
    rating = fields.Selection([("up", "👍 Utile"), ("down", "👎 Inutile")], string="Appréciation")
    rating_comment = fields.Text(string="Commentaire")

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        speaker_label, context_label, context_ref = self._compute_runtime_labels()
        # on met par défaut si le champ est demandé
        if "speaker_label" in fields_list:
            res["speaker_label"] = speaker_label
        if "context_label" in fields_list:
            res["context_label"] = context_label
        if "context_ref" in fields_list:
            res["context_ref"] = context_ref
        return res

    def _compute_runtime_labels(self):
        """Construit 'qui parle' + 'où on est'."""
        user = self.env.user
        speaker_label = f"{user.name} — artisan métallier"

        ctx = self.env.context
        active_model = ctx.get("active_model")
        active_id = ctx.get("active_id") or (ctx.get("active_ids") and ctx.get("active_ids")[0])

        if active_model and active_id:
            record = self.env[active_model].browse(active_id).exists()
            if record:
                display = record.display_name or f"#{active_id}"
                context_label = f"{active_model} — {display}"
                context_ref = f"{active_model}:{active_id}"
                return speaker_label, context_label, context_ref

        return speaker_label, "Général (aucun enregistrement actif)", ""

    def _get_ollama_config(self):
        icp = self.env["ir.config_parameter"].sudo()
        base_url = icp.get_param("voye.ollama_base_url", "http://127.0.0.1:11434")
        model = icp.get_param("voye.ollama_model", "deepseek-r1:7b")
        return base_url, model

    def _build_system_prompt(self) -> str:
        icp = self.env["ir.config_parameter"].sudo()
        sp = icp.get_param("voye.ai_system_prompt")
        if sp and sp.strip():
            base = sp.strip()
        else:
            base = (
                "Tu es l’assistant interne de la Métallerie de Franck. "
                "Tu n'es pas un assistant générique et tu ne cites jamais d'autre entreprise ou marque. "
                "Ton rôle est d’aider à comprendre et relier comptabilité, clients, fournisseurs et atelier. "
                "Réponses courtes, concrètes, en français. "
                "Si une information manque, tu poses 1 à 2 questions. "
                "Tu n’inventes jamais de faits, noms, chiffres ou historiques. "
                "Ne demande jamais de mots de passe, clés ou informations sensibles."
            )

        speaker_label, context_label, context_ref = self._compute_runtime_labels()

        # On injecte cartographie + interlocuteur pour aligner humain/machine
        extra = (
            f"\n\nInterlocuteur: {speaker_label}\n"
            f"Contexte Odoo: {context_label}\n"
        )
        if context_ref:
            extra += f"Réf contexte: {context_ref}\n"

        return base + extra

    def _validate_prompt(self, prompt: str):
        if not prompt or not prompt.strip():
            raise UserError("Écris un prompt.")
        if len(prompt) > 4000:
            raise UserError("Prompt trop long (max 4000 caractères).")

    def _sync_rating_to_log(self):
        self.ensure_one()
        if not self.log_id:
            return
        self.log_id.write({
            "rating": self.rating or False,
            "rating_comment": (self.rating_comment or "").strip() or False,
        })

    def write(self, vals):
        res = super().write(vals)
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

        # Mise à jour affichage des labels dans le wizard
        speaker_label, context_label, context_ref = self._compute_runtime_labels()
        self.speaker_label = speaker_label
        self.context_label = context_label
        self.context_ref = context_ref

        client = OllamaClient(base_url=base_url, model=model, timeout=120)

        t0 = time.time()
        try:
            answer = client.chat(prompt=prompt, system=system, temperature=0.2)
            duration_ms = int((time.time() - t0) * 1000)

            log = self.env["voye.ai.log"].sudo().create({
                "user_id": self.env.user.id,
                "speaker_label": speaker_label,
                "context_label": context_label,
                "context_ref": context_ref,
                "model_name": model,
                "prompt": prompt,
                "answer": answer,
                "duration_ms": duration_ms,
                "state": "ok",
            })

            self.answer = answer
            self.model_name = model
            self.log_id = log.id

            # reset pouces pour la nouvelle réponse
            self.rating = False
            self.rating_comment = False

        except Exception as e:
            duration_ms = int((time.time() - t0) * 1000)
            log = self.env["voye.ai.log"].sudo().create({
                "user_id": self.env.user.id,
                "speaker_label": speaker_label,
                "context_label": context_label,
                "context_ref": context_ref,
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
