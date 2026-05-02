# -*- coding: utf-8 -*-
# from odoo import http


# class TodoTaskType(http.Controller):
#     @http.route('/todo_task_type/todo_task_type', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/todo_task_type/todo_task_type/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('todo_task_type.listing', {
#             'root': '/todo_task_type/todo_task_type',
#             'objects': http.request.env['todo_task_type.todo_task_type'].search([]),
#         })

#     @http.route('/todo_task_type/todo_task_type/objects/<model("todo_task_type.todo_task_type"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('todo_task_type.object', {
#             'object': obj
#         })

