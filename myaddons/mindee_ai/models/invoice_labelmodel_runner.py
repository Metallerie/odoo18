# -*- coding: utf-8 -*-
# invoice_labelmodel_runner.py

import json
import tempfile
from pdf2image import convert_from_path
import pytesseract


def run_invoice_labelmodel(pdf_file, json_model):
    """
    Exécute l'OCR sur un PDF avec un modèle LabelStudio
    et renvoie deux choses :
      - ocr_raw : texte brut complet de la page
      - ocr_zones : liste des zones labelisées avec valeurs OCR
    """

    # Charger le modèle
    with open(json_model, "r", encoding="utf-8") as f:
        model = json.load(f)

    # Convertir PDF en images
    pages = convert_from_path(pdf_file, dpi=300)
    page = pages[0]  # première page
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

                # OCR sur la zone
                crop = page.crop((left, top, right, bottom))
                with tempfile.NamedTemporaryFile(suffix=".PNG", delete=False) as tmp_img:
                    crop_path = tmp_img.name
                    crop.save(crop_path)

                text = pytesseract.image_to_string(crop, lang="fra").strip()
                if not text:
                    text = "NUL"

                ocr_zones.append({
                    "label": label,
                    "row_index": None,   # valeur par défaut, remplacée ensuite
                    "x": x, "y": y, "w": w, "h": h,
                    "text": text
                })

    # 🔹 Numérotation globale haut → bas
    ocr_zones = sorted(ocr_zones, key=lambda z: z["y"])
    for idx, zone in enumerate(ocr_zones, start=1):
        zone["row_index"] = idx

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
        # ⚠️ Toujours renvoyer du JSON minimal en cas d'erreur
        print(json.dumps({"ocr_raw": "", "ocr_zones": [], "error": str(e)}))
        sys.exit(1)
