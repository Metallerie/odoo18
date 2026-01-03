# -*- coding: utf-8 -*-
from odoo import models, fields

class VoyeAiLog(models.Model):
    _name = "voye.ai.log"
    _description = "Voye - Historique IA"
    _order = "create_date desc"

    user_id = fields.Many2one("res.users", string="Utilisateur", required=True, index=True)
    model_name = fields.Char(string="Modèle", index=True)
    prompt = fields.Text(string="Prompt", required=True)
    answer = fields.Text(string="Réponse")
    duration_ms = fields.Integer(string="Durée (ms)")
    state = fields.Selection(
        [("ok", "OK"), ("error", "Erreur")],
        default="ok",
        required=True,
        index=True,
    )
    error_message = fields.Char(string="Erreur")
