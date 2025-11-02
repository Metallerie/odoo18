# -*- coding: utf-8 -*-
"""
create_reconcile_rules.py
Crée automatiquement les règles de rapprochement bancaire à partir des fournisseurs connus.
"""

from odoo import api, SUPERUSER_ID


def run(env):
    Reconcile = env["account.reconcile.model"]
    Account = env["account.account"]
    Company = env.company

    suppliers = [
        {"name": "COMPTOIR COMMERCIAL DU LANGUEDOC", "partner": "CCL", "account": "401103"},
        {"name": "FREE", "partner": "Free SAS", "account": "401104"},
        {"name": "EDF", "partner": "EDF", "account": "401106"},
        {"name": "ALLIANZ", "partner": "Allianz assurance", "account": "401107"},
        {"name": "INFOMANIAK", "partner": "Infomaniak Network SA", "account": "401119"},
        {"name": "POLE VERT", "partner": "Pôle Vert", "account": "401135"},
        {"name": "SOC REGIES", "partner": "SOCIETE EUROPEENNE DE REGIES F", "account": "401139"},
        {"name": "LEBONCOIN", "partner": "LBC FRANCE", "account": "401126"},
    ]

    print("🧹 Suppression des anciennes règles...")
    Reconcile.search([]).unlink()
    env.cr.commit()

    created = 0
    for s in suppliers:
        account = Account.search([("code", "=", s["account"])], limit=1)
        if not account:
            print(f"⚠️ Compte {s['account']} introuvable, règle ignorée.")
            continue

        rule = Reconcile.create({
            "name": f"Paiement {s['partner']}",
            "rule_type": "invoice_matching",
            "match_label": True,
            "match_text_location": s["name"],
            "auto_reconcile": True,
            "line_ids": [(0, 0, {
                "label": s["name"],
                "account_id": account.id,
                "amount_type": "regex",
                "amount_string": "([\\d,\\.]+)",
            })],
        })
        created += 1
        print(f"✅ Règle créée : {rule.name}")

    env.cr.commit()
    print(f"\n🎯 {created} règles créées avec succès.")


def main(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    run(env)


if __name__ == "__main__":
    print("❌ À exécuter depuis le shell Odoo.")
