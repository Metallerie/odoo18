# -*- coding: utf-8 -*-
"""
debug_reconcile_rules.py
--------------------------------
Affiche le contenu réel des règles de rapprochement bancaire (Odoo 18)
et leurs lignes associées.
"""

from odoo import api, SUPERUSER_ID


def run(env):
    ReconcileModel = env["account.reconcile.model"]
    rules = ReconcileModel.search([])
    print(f"🔹 {len(rules)} règles de rapprochement détectées\n")

    for rule in rules:
        print(f"🧩 Règle : {rule.name} (ID: {rule.id})")
        print(f"   - Type : {rule.rule_type}")
        print(f"   - Label : {getattr(rule, 'label', '-')}")
        print(f"   - Match Label : {getattr(rule, 'match_label', False)}")
        print(f"   - Match Narration : {getattr(rule, 'match_narration', False)}")
        print(f"   - Auto Reconcile : {getattr(rule, 'auto_reconcile', False)}")

        # Lignes associées
        if not rule.line_ids:
            print("   ⚠️  Aucune ligne associée (line_ids est vide)")
        else:
            print(f"   🔸 {len(rule.line_ids)} lignes associées :")
            for l in rule.line_ids:
                partner = getattr(l, "partner_id", False)
                account = getattr(l, "account_id", False)
                label = getattr(l, "label", "")
                print(
                    f"      • line_id={l.id} | "
                    f"label='{label or '-'}' | "
                    f"compte={account.display_name if account else '-'} | "
                    f"partenaire={partner.display_name if partner else '-'}"
                )
        print("--------------------------------------------------")

    print("✅ Fin du diagnostic.\n")


def main(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    run(env)


if __name__ == "__main__":
    print("❌ Ce script doit être exécuté via l'Odoo shell.")
