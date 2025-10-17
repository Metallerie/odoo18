# -*- coding: utf-8 -*-
# invoice_labelmodel_runner.py
# OCR par zones + regroupement lignes (ocr_rows)
# Version avec suppression des "NUL" + enrichissement Qté/Unité

import json
import tempfile
import re
from pdf2image import convert_from_path
import pytesseract
from PIL import ImageOps

# Labels à ignorer (zones structurelles LS)
IGNORE_LABELS = {"Header", "Table", "Footer", "Document", "Document type",
                 "Table Header", "Table Row", "Table End", "Table Total"}

def preprocess_crop(crop):
    """Améliore le contraste avant OCR"""
    crop = crop.convert("L")  # niveaux de gris
    crop = ImageOps.autocontrast(crop)  # boost contraste
    return crop

def enrich_with_regex(ocr_rows, ocr_raw):
    """
    Complète Qté et Unité si manquants, via regex sur ocr_raw ou calcul
    """
    pattern = re.compile(
        r"(?P<ref>\d{4,})\s+(?P<desc>.+?)\s+(?P<qty>\d+)\s+(?P<unit>[A-Z]+)\s+(?P<price>\d+,\d+)\s+(?P<amount>\d+,\d+)",
        re.UNICODE
    )

    for row in ocr_rows:
        labels = {c["label"]: c["text"] for c in row["cells"]}
        if "Reference" not in labels:
            continue
        if "Quantity" in labels and "Unité" in labels:
            continue  # déjà complet

        ref = labels["Reference"]
        match = None
        for m in pattern.finditer(ocr_raw):
            if m.group("ref") == ref:
                match = m
                break

        if match:
            qty = match.group("qty")
            unit = match.group("unit")
            if "Quantity" not in labels:
                row["cells"].append({"label": "Quantity", "text": qty})
            if "Unité" not in labels:
                row["cells"].append({"label": "Unité", "text": unit})

        # Fallback calcul qty si montant/prix présents
        labels = {c["label"]: c["text"] for c in row["cells"]}
        if "Quantity" not in labels and "Unit Price" in labels and "Amount HT" in labels:
            try:
                price = float(labels["Unit Price"].replace(",", "."))
                amount = float(labels["Amount HT"].replace(",", "."))
                qty = round(amount / price)
                row["cells"].append({"label": "Quantity", "text": str(qty)})
            except Exception:
                pass

    return ocr_rows

def run_invoice_labelmodel(pdf_file, json_model):
    """
    Exécute l'OCR sur un PDF avec un modèle LabelStudio
    Retourne :
      - ocr_raw : texte brut complet
      - ocr_zones : toutes les zones utiles (hors header/footer, sans NUL)
      - ocr_rows : regroupement par lignes (sans NUL, enrichi Qté/Unité)
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

                # ignorer les zones inutiles OU les NUL
                if label in IGNORE_LABELS or label == "NUL":
                    continue

                # Position en pixels
                x, y, w, h = zone["x"], zone["y"], zone["width"], zone["height"]
                left = int((x / 100) * img_w)
                top = int((y / 100) * img_h)
                right = int(((x + w) / 100) * img_w)
                bottom = int(((y + h) / 100) * img_h)

                crop = page.crop((left, top, right, bottom))
                crop = preprocess_crop(crop)  # prétraitement contraste

                with tempfile.NamedTemporaryFile(suffix=".PNG", delete=False) as tmp_img:
                    crop_path = tmp_img.name
                    crop.save(crop_path)

                text = pytesseract.image_to_string(crop, lang="fra").strip()

                # ⚠️ on ignore les cases vides
                if not text:
                    continue

                ocr_zones.append({
                    "label": label,
                    "x": round(x, 2),  # 2 décimales
                    "y": round(y, 2),
                    "w": round(w, 2),
                    "h": round(h, 2),
                    "text": text
                })

    # === Regroupement par lignes ===
    row_index = 0
    rows = []
    current_y = None
    tolerance = 2.0  # tolérance sur Y (% hauteur doc)

    for zone in sorted(ocr_zones, key=lambda z: (z["y"], z["x"])):
        if current_y is None or abs(zone["y"] - current_y) > tolerance:
            row_index += 1
            current_y = zone["y"]
            rows.append({"row_index": row_index, "cells": []})

        rows[-1]["cells"].append({
            "label": zone["label"],
            "text": zone["text"]
        })

    # Enrichir avec regex et calcul fallback
    rows = enrich_with_regex(rows, ocr_raw)

    return {
        "ocr_raw": ocr_raw,
        "ocr_zones": ocr_zones,  # zones utiles uniquement
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
