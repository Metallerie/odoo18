# -*- coding: utf-8 -*-
# invoice_labelmodel_runner.py
# OCR par zones + regroupement lignes (ocr_rows)

import json
import tempfile
from pdf2image import convert_from_path
import pytesseract

def run_invoice_labelmodel(pdf_file, json_model):
    """
    Exécute l'OCR sur un PDF avec un modèle LabelStudio
    Retourne :
      - ocr_raw : texte brut complet
      - ocr_zones : toutes les zones extraites
      - ocr_rows : regroupement par lignes
    """

    # Charger le modèle
    with open(json_model, "r", encoding="utf-8") as f:
        model = json.load(f)

    # Convertir PDF en images
    pages = convert_from_path(pdf_file, dpi=300)
    page = pages[0]
    img_w, img_h = page.size

    # OCR brut complet
    ocr_raw = pytesseract.image_to_string(page, lang="fra")

    # OCR par zones Label Studio
    ocr_zones = []
    for entry in model:
        for key, zones in entry.items():
            if not isinstance(zones, list):
                continue
            for zone in zones:
                if not isinstance(zone, dict):
                    continue

                label_list = zone.get("rectanglelabels", [])
                label = label_list[0] if label_list else "NUL"

                # Position en pixels
                x, y, w, h = zone["x"], zone["y"], zone["width"], zone["height"]
                left = int((x / 100) * img_w)
                top = int((y / 100) * img_h)
                right = int(((x + w) / 100) * img_w)
                bottom = int(((y + h) / 100) * img_h)

                crop = page.crop((left, top, right, bottom))
                with tempfile.NamedTemporaryFile(suffix=".PNG", delete=False) as tmp_img:
                    crop_path = tmp_img.name
                    crop.save(crop_path)

                text = pytesseract.image_to_string(crop, lang="fra").strip()
                if not text:
                    text = "NUL"

                ocr_zones.append({
                    "label": label,
                    "x": x, "y": y, "w": w, "h": h,
                    "text": text
                })

    # === Regroupement par lignes ===
    row_index = 0
    rows = []
    current_y = None
    tolerance = 2.0  # tolérance sur Y (en % hauteur doc)

    for zone in sorted(ocr_zones, key=lambda z: (z["y"], z["x"])):
        if current_y is None or abs(zone["y"] - current_y) > tolerance:
            # nouvelle ligne
            row_index += 1
            current_y = zone["y"]
            rows.append({"row_index": row_index, "cells": []})

        rows[-1]["cells"].append({
            "label": zone["label"],
            "text": zone["text"]
        })

    return {
        "ocr_raw": ocr_raw,
        "ocr_zones": ocr_zones,
        "ocr_rows": rows
    }

# === Main pour test console ===
if __name__ == "__main__":
    import sys
    try:
        if len(sys.argv) != 3:
            print(json.dumps({"error": "Usage: python invoice_labelmodel_runner.py <pdf> <model.json>"}))
            sys.exit(1)

        pdf_file = sys.argv[1]
        json_file = sys.argv[2]

        data = run_invoice_labelmodel(pdf_file, json_file)
        print(json.dumps(data, indent=2, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"ocr_raw": "", "ocr_zones": [], "ocr_rows": [], "error": str(e)}))
        sys.exit(1)
