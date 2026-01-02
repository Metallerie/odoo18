# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class VoyeController(http.Controller):

    @http.route("/voye/chart_of_accounts", type="json", auth="user", methods=["POST"], csrf=False)
    def voye_chart_of_accounts(self, include_deprecated=False, company_id=None):
        """
        Retourne le plan comptable complet pour la société courante (ou company_id si autorisée).
        Auth: user (session Odoo). Utilisable depuis Voye via un compte technique.
        """
        env = request.env

        # Sécurité multi-sociétés : on n’autorise company_id que s’il est dans les sociétés accessibles
        if company_id:
            allowed = env.companies.ids  # sociétés accessibles par l'utilisateur
            if company_id not in allowed:
                return {"error": "company_id not allowed", "allowed_company_ids": allowed}

        svc = env["voye.chart_of_accounts.service"]
        data = svc.get_full_chart_of_accounts(company_id=company_id, include_deprecated=bool(include_deprecated))
        return data

    @http.route("/voye/ping", type="http", auth="user", methods=["GET"], csrf=False)
    def voye_ping(self, **kwargs):
        """Petit endpoint de test."""
        return "ok"
