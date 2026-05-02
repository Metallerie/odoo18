# -*- coding: utf-8 -*-

from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    todo_type_id = fields.Many2one(
        comodel_name="todo.task.type",
        string="Type de tâche",
        ondelete="set null",
    )

    todo_type_color = fields.Integer(
        string="Couleur du type",
        related="todo_type_id.color",
        store=False,
    )
