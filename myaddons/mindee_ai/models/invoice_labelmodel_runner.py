# -*- coding: utf-8 -*-
# invoice_labelmodel_runner.py

import json
import tempfile
from pdf2image import convert_from_path
import pytesseract


def run_invoice_labelmodel(pdf_file, json_model):
    """
    OCR + LabelStudio avec numérotation des lignes basée
    sur la première cellule à gauche (x minimal).
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

    # OCR zones
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

                x, y, w, h = zone["x"], zone["y"], zone["width"], zone["height"]
                left = int((x / 100) * img_w)
                top = int((y / 100) * img_h)
                right = int(((x + w) / 100) * img_w)
                bottom = int(((y + h) / 100) * img_h)

                crop = page.crop((left, top, right, bottom))
                with tempfile.NamedTemporaryFile(suffix=".PNG", delete=False) as tmp_img:
                    crop_path = tmp_img.name
                    crop.save(crop_path)

                text = pytesseract.image_to_string(crop, lang="fra").strip() or "NUL"

                ocr_zones.append({
                    "label": label,
                    "row_index": None,
                    "x": x, "y": y, "w": w, "h": h,
                    "text": text
                })

    # 🔹 Numérotation basée sur la première cellule (gauche)
    ocr_zones = sorted(ocr_zones, key=lambda z: (z["y"], z["x"]))
    row_index = 0
    rows = []  # mémorise (y, h, idx) pour chaque ligne créée

    for zone in ocr_zones:
        if zone["x"] < 15:  # seuil arbitraire : x < 15% = cellule de gauche
            row_index += 1
            base_y, base_h = zone["y"], zone["h"]
            zone["row_index"] = row_index
            rows.append((base_y, base_h, row_index))
        else:
            # Cherche la ligne correspondante dans rows
            for (y0, h0, idx) in rows[::-1]:
                if y0 - 0.5 <= zone["y"] <= y0 + h0 + 0.5:
                    zone["row_index"] = idx
                    break
            if zone["row_index"] is None:
                # rien trouvé → nouvelle ligne
                row_index += 1
                zone["row_index"] = row_index
                rows.append((zone["y"], zone["h"], row_index))

    return {
        "ocr_raw": ocr_raw,
        "ocr_zones": ocr_zones
    }


if __name__ == "__main__":
    import sys
    try:
        if len(sys.argv) != 3:
            print(json.dumps({"ocr_raw": "", "ocr_zones": [], "error": "Bad arguments"}))
            sys.exit(1)

        pdf_file = sys.argv[1]
        json_file = sys.argv[2]

        data = run_invoice_labelmodel(pdf_file, json_file)
        print(json.dumps(data, indent=2, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"ocr_raw": "", "ocr_zones": [], "error": str(e)}))
        sys.exit(1)
