# -*- coding: utf-8 -*-
from odoo import api, models


class VoyeChartOfAccountsService(models.AbstractModel):
    """
    Service: export du plan comptable complet de la société courante.
    Objectif: fournir un référentiel fiable à l'IA (pas d'écritures ici).
    """
    _name = "voye.chart_of_accounts.service"
    _description = "Voye - Chart of Accounts Service"

    @api.model
    def get_full_chart_of_accounts(self, company_id=None, include_deprecated=False):
        """
        Retourne le plan comptable complet (account.account) sous forme JSON-friendly.

        :param company_id: (int|None) société ciblée. Par défaut: env.company.
        :param include_deprecated: (bool) inclure les comptes obsolètes.
        :return: dict {meta: {...}, accounts: [ ... ]}
        """
        company = self.env["res.company"].browse(company_id) if company_id else self.env.company
        company = company.sudo()

        domain = [("company_id", "=", company.id)]
        if not include_deprecated:
            domain.append(("deprecated", "=", False))

        # Champs sûrs et utiles (évite de renvoyer des tonnes de choses)
        fields = [
            "id",
            "code",
            "name",
            "deprecated",
            "reconcile",
            "account_type",
            "company_id",
        ]

        accounts = self.env["account.account"].sudo().search(domain, order="code asc")
        # read() est plus rapide/compact qu'un for a in accounts quand tu veux du JSON
        rows = accounts.read(fields)

        # Normalisation minimale (account_type peut être string/selection selon versions)
        for r in rows:
            # company_id est [id, name]
            if isinstance(r.get("company_id"), list):
                r["company_id"] = r["company_id"][0]

        return {
            "meta": {
                "source": "Odoo ORM: account.account",
                "company_id": company.id,
                "company_name": company.name,
                "count": len(rows),
                "include_deprecated": bool(include_deprecated),
            },
            "accounts": rows,
        }
