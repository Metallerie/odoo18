# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    x_target_journal_code = fields.Selection(
        selection="_get_all_journal_selection",
        string="Journal cible",
    )

    @api.model
    def _get_all_journal_selection(self):
        journals = self.env["account.journal"].sudo().search([
            ("company_id", "=", self.env.company.id)
        ], order="code, name")

        return [
            (str(journal.id), f"{journal.code} - {journal.name}")
            for journal in journals
        ]

    @api.onchange("x_target_journal_code")
    def _onchange_x_target_journal_code(self):
        for move in self:
            if not move.x_target_journal_code:
                continue

            journal = self.env["account.journal"].sudo().browse(
                int(move.x_target_journal_code)
            )

            if not journal.exists():
                continue

            move.journal_id = journal

            if journal.type == "purchase":
                move.move_type = "in_invoice"
            elif journal.type == "sale":
                move.move_type = "out_invoice"
            else:
                move.move_type = "entry"
