# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import AccessError


class VoyeAiLog(models.Model):
    _name = "voye.ai.log"
    _description = "Voye - Historique IA"
    _order = "create_date desc"

    # Qui parle / contexte (lisible + technique)
    speaker_label = fields.Char(string="Interlocuteur", readonly=True, index=True)
    context_label = fields.Char(string="Contexte", readonly=True, index=True)
    context_ref = fields.Char(string="Réf contexte", readonly=True, index=True)  # ex: account.move:123

    user_id = fields.Many2one(
        "res.users",
        string="Utilisateur",
        required=True,
        index=True,
        readonly=True,
    )
    model_name = fields.Char(string="Modèle IA", index=True, readonly=True)
    prompt = fields.Text(string="Prompt", required=True, readonly=True)
    answer = fields.Text(string="Réponse", readonly=True)
    duration_ms = fields.Integer(string="Durée (ms)", readonly=True)

    state = fields.Selection(
        [("ok", "OK"), ("error", "Erreur")],
        default="ok",
        required=True,
        index=True,
        readonly=True,
    )
    error_message = fields.Char(string="Erreur", readonly=True)

    # Notation
    rating = fields.Selection(
        [("up", "👍 Utile"), ("down", "👎 Inutile")],
        string="Appréciation",
        index=True,
    )
    rating_comment = fields.Text(string="Commentaire")

    def write(self, vals):
        """
        Sécurité: seuls rating / rating_comment sont modifiables par les utilisateurs.
        Tout le reste est figé (traçabilité).
        """
        allowed = {"rating", "rating_comment"}
        if not self.env.is_superuser():
            if any(k not in allowed for k in vals.keys()):
                raise AccessError(_("Tu ne peux modifier que l’appréciation et le commentaire."))
        return super().write(vals)
