#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import subprocess

# --- Contexte Odoo ---
sys.path.append('/data/odoo/metal-odoo18-p8179')
os.environ['ODOO_RC'] = '/data/odoo/metal-odoo18-p8179/odoo18.conf'

import odoo
from odoo import api, tools, sql_db

DB = "metal-prod-18"

tools.config.parse_config([])
odoo.service.server.load_server_wide_modules()

db = sql_db.db_connect(DB)
cr = db.cursor()
env = api.Environment(cr, 1, {})


# -------- Utils ----------
def normalize_text(val):
    return (val or "").strip().lower()


def run_tesseract(pdf_path):
    """Appelle ton script tesseract_runner.py et récupère le JSON"""
    venv_python = "/data/odoo/odoo18-venv/bin/python3"
    tesseract_script = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/scripts/tesseract_runner.py"

    result = subprocess.run(
        [venv_python, tesseract_script, pdf_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding="utf-8"
    )
    if result.returncode != 0:
        print("❌ Erreur OCR:", result.stderr)
        sys.exit(1)

    return json.loads(result.stdout)


def test_rules(pdf_path):
    ocr_data = run_tesseract(pdf_path)

    raw_text = " ".join(sum([p.get("phrases", []) for p in ocr_data.get("pages", [])], []))
    parsed = ocr_data["pages"][0].get("parsed", {})

    invoice_number = parsed.get("invoice_number", "")
    invoice_date = parsed.get("invoice_date", "")
    partner_name_ocr = parsed.get("supplier_name", "")

    print("🔎 OCR PARSED:", parsed)
    print("🔎 supplier_name:", partner_name_ocr or "(vide)")
    print("🔎 raw_text preview:", raw_text[:200], "…\n")  # affiche les 200 premiers caractères

    # Charger règles actives
    rules = env["ocr.configuration.rule"].search([("active", "=", True)], order="sequence")
    print(f"📌 {len(rules)} règles trouvées\n")

    for rule in rules:
        value = ""
        if rule.variable == "partner_name":
            # si supplier_name vide → on prend raw_text
            value = partner_name_ocr or raw_text
        elif rule.variable == "invoice_number":
            value = invoice_number
        elif rule.variable == "invoice_date":
            value = invoice_date

        matched = False
        if rule.condition_type == "text" and rule.value_text:
            val = normalize_text(value)
            cmp = normalize_text(rule.value_text)

            if rule.operator == "contains":
                matched = cmp in val
            elif rule.operator == "==":
                matched = val == cmp
            elif rule.operator == "startswith":
                matched = val.startswith(cmp)
            elif rule.operator == "endswith":
                matched = val.endswith(cmp)

            # 🔥 fallback auto pour les partenaires
            if rule.variable == "partner_name" and not matched:
                if cmp in val:
                    matched = True
                    print(f"⚡ fallback contains appliqué pour {rule.name}")

        print(f"➡️ Règle {rule.name} ({rule.variable} {rule.operator} {rule.value_text}) "
              f"sur '{(value or '')[:80]}' → {matched}")

        if matched and rule.partner_id:
            print(f"\n✅ PARTNER CHOISI : {rule.partner_id.name} (ID={rule.partner_id.id})\n")
            break


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 test_rules_live.py <fichier_pdf>")
        sys.exit(1)

    test_rules(sys.argv[1])
