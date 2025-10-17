# -*- coding: utf-8 -*-
# ocr_totals_debug.py
# Test extraction des totaux (HT, TVA, TTC) depuis le JSON OCR

import json
import re
import sys


def to_float(val):
    """Convertit un texte en float sécurisé."""
    if not val:
        return 0.0
    val = val.replace(" ", "").replace(",", ".")
    if not re.match(r"^-?\d+(\.\d+)?$", val):
        return 0.0
    try:
        return float(val)
    except Exception:
        return 0.0


def extract_totals(json_file):
    with open(json_file, "r", encoding="utf-8") as f:
        zones = json.load(f)

    total_ht = 0.0
    total_tva = 0.0
    total_ttc = 0.0

    for z in zones:
        label = (z.get("label") or "").lower()
        text = (z.get("text") or "").strip()

        if label in ["total ht", "total net h.t", "total brut ht"]:
            total_ht = to_float(re.sub(r"[^\d,\.]", "", text))

        elif label in ["tva", "total tva"]:
            total_tva = to_float(re.sub(r"[^\d,\.]", "", text))

        elif label in ["total ttc", "net a payer"]:
            total_ttc = to_float(re.sub(r"[^\d,\.]", "", text))

    print("=== Totaux détectés ===")
    print(f"Montant HT : {total_ht:.2f} €")
    print(f"TVA        : {total_tva:.2f} €")
    print(f"Montant TTC: {total_ttc:.2f} €")

    # Création d’une ligne factice
    print("\n=== Ligne produit factice ===")
    print({
        "name": "Produit en attente (OCR)",
        "quantity": 1,
        "price_unit": total_ht,
        "tax": total_tva,
        "total": total_ttc,
    })


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 ocr_totals_debug.py <json_file>")
        sys.exit(1)

    extract_totals(sys.argv[1])
