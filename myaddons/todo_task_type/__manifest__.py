# -*- coding: utf-8 -*-

{
    "name": "To-Do Task Type",
    "version": "18.0.1.0.0",
    "category": "Productivity",
    "summary": "Ajoute des types colorés aux tâches To-Do",
    "depends": ["project_todo"],
    "data": [
        "security/ir.model.access.csv",
        "views/todo_task_type_views.xml",
        "views/project_task_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
