# -*- coding: utf-8 -*-
import sys
import json

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def build_rows(zones):
    rows = []
    row_index = 0

    # Trier toutes les zones par Y croissant
    sorted_zones = sorted(zones, key=lambda z: round(z["y"], 2))

    for z in sorted_zones:
        label = z.get("label", "")
        text = z.get("text", "").strip()

        # ignorer si vide, ou header/footer/table
        if not text or label in ["Header", "Footer", "Table"]:
            continue

        # arrondir coordonnées
        x = round(z.get("x", 0), 2)
        y = round(z.get("y", 0), 2)
        w = round(z.get("w", 0), 2)
        h = round(z.get("h", 0), 2)

        # si c’est une nouvelle ligne
        if not rows or abs(y - rows[-1]["y"]) > 1.5:  
            row_index += 1
            rows.append({
                "row_index": row_index,
                "y": y,
                "cells": []
            })

        # ajouter cellule si pas NUL
        if label != "NUL":
            rows[-1]["cells"].append({
                "label": label,
                "text": text,
                "x": x, "y": y, "w": w, "h": h
            })

    # Nettoyer les doublons dans chaque ligne
    for row in rows:
        clean_cells = []
        seen_texts = set()
        for cell in row["cells"]:
            if cell["text"] in seen_texts:
                continue
            seen_texts.add(cell["text"])
            clean_cells.append(cell)
        row["cells"] = clean_cells

    return rows

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 invoice_labelmodel_runner.py input.json output.json")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    data = load_json(input_file)
    zones = data.get("ocr_zones_all", [])

    rows = build_rows(zones)

    result = {
        "ocr_raw": data.get("ocr_raw", ""),
        "rows": rows
    }

    save_json(result, output_file)
    print(f"✅ JSON nettoyé enregistré dans {output_file}")

if __name__ == "__main__":
    main()
