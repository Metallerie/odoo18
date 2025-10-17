# -*- coding: utf-8 -*-
# ocr_console_debug.py
# Test OCR LabelStudio runner → affichage console avec tri produit / incomplet

import json
import subprocess
import sys

def to_float(val):
    """Convertit une valeur OCR en float sécurisé"""
    if not val:
        return 0.0
    val = str(val).replace(" ", "").replace(",", ".")
    try:
        return float(val)
    except:
        return 0.0

def main():
    if len(sys.argv) != 3:
        print("Usage: python ocr_console_debug.py <facture.pdf> <modele.json>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    json_file = sys.argv[2]

    # Chemins adaptés à ton environnement
    venv_python = "/data/odoo/odoo18-venv/bin/python3"
    runner_path = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/models/invoice_labelmodel_runner.py"

    # Lancer le runner
    result = subprocess.run(
        [venv_python, runner_path, pdf_file, json_file],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=180, encoding="utf-8"
    )

    if result.stderr.strip():
        print("⚠️ STDERR:", result.stderr)

    if not result.stdout.strip():
        print("❌ Runner n'a rien renvoyé")
        sys.exit(1)

    try:
        ocr_result = json.loads(result.stdout)
    except Exception as e:
        print("❌ Erreur JSON runner:", e)
        sys.exit(1)

    zones = ocr_result.get("ocr_zones", []) or []

    # --- Regroupement par Y ---
    rows = {}
    for z in zones:
        if z.get("label") in ["Reference", "Description", "Quantity", "Unité", "Unit Price", "Amount HT", "VAT"]:
            y = round(float(z.get("y", 0)), 1)
            if y not in rows:
                rows[y] = {}
            rows[y][z.get("label")] = (z.get("text") or "").strip()

    # --- Affichage console ---
    for y, data in sorted(rows.items()):
        ref = data.get("Reference", "")
        desc = data.get("Description", "")
        qty = data.get("Quantity", "")
        uom = data.get("Unité", "")
        pu = data.get("Unit Price", "")
        montant = data.get("Amount HT", "")

        qty_val = to_float(qty)
        pu_val = to_float(pu)
        montant_val = to_float(montant)

        if qty_val > 0 and pu_val > 0 and montant_val > 0:
            print(f"✅ Ligne produit : Ref={ref}, Desc={desc}, Qté={qty}, U={uom}, PU={pu}, Montant={montant}")
        else:
            print(f"⚠️ Ligne OCR incomplète : Ref={ref}, Desc={desc}, Qté={qty}, U={uom}, PU={pu}, Montant={montant}")


if __name__ == "__main__":
    main()
