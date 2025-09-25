#!/usr/bin/env python3
import sys
import os
import pytesseract
from pdf2image import convert_from_path
import re
import json
import cv2
import numpy as np

# 📥 Vérifie l'argument
if len(sys.argv) < 2:
    print("❌ Usage: python3 tesseract_runner4.py <fichier.pdf>")
    sys.exit(1)

pdf_path = sys.argv[1]
if not os.path.exists(pdf_path):
    print(f"❌ Fichier introuvable : {pdf_path}")
    sys.exit(1)

print(f"📥 Lecture du fichier : {pdf_path}")

# 📄 Conversion PDF → images
images = convert_from_path(pdf_path)
results = []

# --- Chargement regex depuis ton fichier JSON ---
regex_file = os.path.join(
    os.path.dirname(__file__),
    "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/regex/ccl_regex.json"
)
with open(regex_file, "r", encoding="utf-8") as f:
    regex_patterns = json.load(f)

def parse_fields(text, data):
    """Extrait les champs via regex (retourne valeurs + y pour zonage)"""
    parsed = {}
    for key, pattern in regex_patterns.items():
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            value = match.group(1).strip()
            # retrouver la coordonnée Y correspondant à la valeur
            y_coord = None
            for i, word in enumerate(data["text"]):
                if value in word:
                    y_coord = data["top"][i]
                    break
            parsed[key] = {"value": value, "y": y_coord}
    return parsed

def classify_zone(y, page_height):
    """Classe une donnée selon sa position Y en pourcentage"""
    if y is None:
        return "body"  # fallback
    if y < page_height * 0.2:
        return "header"
    elif y < page_height * 0.8:
        return "body"
    else:
        return "footer"

# --- OCR et parsing ---
for i, pil_img in enumerate(images, start=1):
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    height, width = img.shape[:2]

    # OCR avec bbox
    data = pytesseract.image_to_data(img, lang="fra", output_type=pytesseract.Output.DICT)
    text = " ".join(data["text"])

    # Extraction regex + Y coord
    parsed_with_y = parse_fields(text, data)

    # Version brute (valeurs uniquement)
    parsed = {k: v["value"] for k, v in parsed_with_y.items()}

    # Classement dynamique en zones
    zones = {"header": {}, "body": {}, "footer": {}}
    for key, field in parsed_with_y.items():
        zone = classify_zone(field["y"], height)
        zones[zone][key] = field["value"]

    results.append({
        "page": i,
        "parsed": parsed,   # JSON brut (valeurs uniquement)
        "zones": zones      # classé par zones dynamiques
    })

# --- Affichage final ---
print("✅ OCR + parsing terminé")

# JSON brut
print("\n📊 Résultat brut")
print(json.dumps([{"page": r["page"], "parsed": r["parsed"]} for r in results],
                 indent=2, ensure_ascii=False))

# JSON réorganisé par zones dynamiques
print("\n🗂️ Données classées par zones (header/body/footer dynamiques)")
for page in results:
    print(json.dumps(page["zones"], indent=2, ensure_ascii=False))
