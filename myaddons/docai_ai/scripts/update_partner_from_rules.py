# -*- coding: utf-8 -*-
"""
Met à jour les partenaires des lignes de relevé bancaire
en fonction des règles de rapprochement bancaires existantes.
"""

from odoo import api, SUPERUSER_ID

def run(env):
    ReconcileModel = env["account.reconcile.model"]
    BankLine = env["account.bank.statement.line"]

    rules = ReconcileModel.search([])
    print(f"🔹 {len(rules)} règles trouvées")

    lines = BankLine.search([])
    print(f"🔹 {len(lines)} lignes de relevé trouvées")

    updated = 0

    for line in lines:
        if line.partner_id:
            continue

        label = (line.name or "").lower()

        for rule in rules:
            # Vérifie la présence d'une condition sur le libellé
            match_texts = []

            # Certaines règles ont match_label=True et match_text_location vide
            if getattr(rule, "match_label", False) and rule.match_narration:
                match_texts.append(rule.match_narration)
            elif rule.match_text_location:
                match_texts.extend(rule.match_text_location.split(","))

            for match in match_texts:
                match = match.strip().lower()
                if match and match in label:
                    if rule.partner_id:
                        line.partner_id = rule.partner_id.id
                        updated += 1
                        print(f"✅ {line.name[:50]}... → {rule.partner_id.name}")
                        break

    print(f"\n✅ {updated} lignes mises à jour selon les règles.\n")

def main(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    run(env)

if __name__ == "__main__":
    print("❌ Ce script doit être exécuté via l'Odoo shell.")
