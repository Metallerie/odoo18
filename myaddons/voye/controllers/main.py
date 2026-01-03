# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import UserError

from ..services.ollama_client import OllamaClient

class VoyeChatController(http.Controller):

    @http.route("/voye/chat", type="json", auth="user", methods=["POST"], csrf=False)
    def voye_chat(self, prompt=None, **kwargs):
        if not prompt:
            raise UserError("prompt manquant")

        icp = request.env["ir.config_parameter"].sudo()
        base_url = icp.get_param("voye.ollama_base_url", "http://127.0.0.1:11434")
        model = icp.get_param("voye.ollama_model", "deepseek-r1:latest")

        client = OllamaClient(base_url=base_url, model=model)
        answer = client.chat(prompt)
        return {"answer": answer}
