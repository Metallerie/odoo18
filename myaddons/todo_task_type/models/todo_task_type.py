# -*- coding: utf-8 -*-

from odoo import fields, models


class TodoTaskType(models.Model):
    _name = "todo.task.type"
    _description = "Type de tâche To-Do"
    _order = "sequence, name"

    name = fields.Char(string="Nom", required=True)
    color = fields.Integer(string="Couleur", default=0)
    sequence = fields.Integer(string="Séquence", default=10)
    active = fields.Boolean(string="Actif", default=True)
