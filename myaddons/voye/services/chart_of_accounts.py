# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
from odoo import api, models


class VoyeChartOfAccountsService(models.AbstractModel):
    _name = "voye.chart_of_accounts.service"
    _description = "Voye - Chart of Accounts Service"

    @api.model
    def get_full_chart_of_accounts(self, company_id=None, include_deprecated=False):
        company = self.env["res.company"].browse(company_id) if company_id else self.env.company
        company = company.sudo()

        domain = [("company_ids", "in", [company.id])]
        if not include_deprecated:
            domain.append(("deprecated", "=", False))

        fields = ["id", "code", "name", "deprecated", "reconcile", "account_type", "company_ids"]

        accounts = self.env["account.account"].sudo().search(domain, order="code asc")
        rows = accounts.read(fields)

        return {
            "meta": {
                "source": "Odoo ORM: account.account",
                "company_id": company.id,
                "company_name": company.name,
                "count": len(rows),
                "include_deprecated": bool(include_deprecated),
                "company_filter_mode": "company_ids",
            },
            "accounts": rows,
        }
