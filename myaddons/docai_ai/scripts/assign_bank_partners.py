# -*- coding: utf-8 -*-
#assign_bank_partners.py.
from odoo import models, api

class BankPartnerAssign(models.AbstractModel):
    _name = "docai.bank.partner.assign"
    _description = "Assignation automatique du partenaire sur lignes bancaires"

    @api.model
    def assign_bank_partners(self):
        Mapping = self.env['account.reconcile.model.partner.mapping']

        # Récupération des correspondances
        mappings = Mapping.search([])
        if not mappings:
            return "Aucune correspondance définie."

        # Sélection des lignes bancaires SANS partenaire
        self.env.cr.execute("""
            SELECT id, payment_ref
            FROM account_bank_statement_line
            WHERE partner_id IS NULL
        """)
        lines = self.env.cr.fetchall()

        count = 0

        for (line_id, payment_ref) in lines:
            txt = (payment_ref or "").upper()
            for m in mappings:
                key = (m.payment_ref_regex or "").upper()
                if key and key in txt:
                    # Pas de synchronisation → aucune modification comptable
                    self.env.cr.execute("""
                        UPDATE account_bank_statement_line
                        SET partner_id = %s
                        WHERE id = %s
                    """, (m.partner_id.id, line_id))
                    count += 1
                    break

        self.env.cr.commit()
        return f"{count} lignes mises à jour."
