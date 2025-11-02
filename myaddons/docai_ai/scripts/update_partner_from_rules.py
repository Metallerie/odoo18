# -*- coding: utf-8 -*-
"""
update_partner_from_rules.py
--------------------------------
Met à jour les partenaires des lignes de relevé bancaire
en fonction des règles de rapprochement bancaire (account.reconcile.model).

Usage depuis le shell Odoo :
    odoo shell -d metal-prod-18
    >>> exec(open('/data/odoo/metal-odoo18-p8179/myaddons/docai_ai/scripts/update_partner_from_rules.py').read())
"""

from odoo import api, SUPERUSER_ID


def run(env):
    ReconcileModel = env["account.reconcile.model"]
    BankLine = env["account.bank.statement.line"]

    rules = ReconcileModel.search([])
    print(f"🔹 {len(rules)} règles de rapprochement détectées\n")

    lines = BankLine.search([])
    print(f"🔹 {len(lines)} lignes de relevé à analyser\n")

    updated = 0

    for line in lines:
        if line.partner_id:
            continue

        label = (line.name or "").lower()

        for rule in rules:
            # On vérifie les conditions d'une règle
            has_match_label = getattr(rule, "match_label", False)
            has_match_narration = getattr(rule, "match_narration", False)
            keyword = (rule.label or "").strip().lower()

            if not keyword:
                continue

            # Si le libellé contient le mot-clé défini dans la règle
            if keyword in label:
                # On regarde la première ligne d'action de la règle
                line_rule = rule.line_ids[:1]
                if line_rule and getattr(line_rule, "account_id", False):
                    partner = getattr(line_rule, "partner_id", False)
                    if partner:
                        line.partner_id = partner.id
                        updated += 1
                        print(f"✅ {line.name[:60]}... → {partner.display_name}")
                        break

    print(f"\n✅ {updated} lignes bancaires mises à jour selon les règles.\n")


def main(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    run(env)


if __name__ == "__main__":
    print("❌ Ce script doit être exécuté via l'Odoo shell (pas directement).")
