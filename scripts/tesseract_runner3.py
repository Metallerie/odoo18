#!/usr/bin/env python3
import sys
import os
import json
import re
from pdf2image import convert_from_path
import pytesseract

# 📂 Chemin vers la bibliothèque regex JSON
REGEX_JSON_PATH = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/regex/ccl_regex.json"

# ----------- 🔧 Charger les regex ----------------
def load_regex_library():
    if not os.path.exists(REGEX_JSON_PATH):
        print("⚠️ Aucune bibliothèque trouvée, création d'un fichier neuf.")
        return {"update_count": 0, "fields": {}}
    with open(REGEX_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

# ----------- 💾 Sauvegarder ----------------
def save_regex_library(lib):
    with open(REGEX_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=2)

# ----------- 🔍 Appliquer regex ----------------
def apply_regex(text, regex_library):
    results = {}
    for field, patterns in regex_library["fields"].items():
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                results[field] = match.group(1) if match.groups() else match.group(0)
                break
    return results

# ----------- 🛠️ Mettre à jour JSON ----------------
def update_library(lib, extracted):
    updated = False
    for key, value in extracted.items():
        if not value:
            continue
        if key not in lib["fields"]:
            lib["fields"][key] = []
        # Vérifie si déjà présent
        if not any(value in p for p in lib["fields"][key]):
            lib["fields"][key].append(value)
            updated = True
    if updated:
        lib["update_count"] += 1
    return lib

# ----------- 📑 Parsing OCR ----------------
def parse_invoice_text(text, regex_library):
    data = {
        "invoice_number": None,
        "invoice_date": None,
        "siren": None,
        "siret": None,
        "tva_intracom": None,
        "iban": None,
        "bic": None,
        "total_ht": None,
        "total_tva": None,
        "total_ttc": None,
        "line_items": []   # ✅ toujours liste
    }

    # Appliquer les regex de la bibliothèque
    extracted = apply_regex(text, regex_library)
    for key in data:
        if key in extracted:
            if key == "line_items":   # ⚡ sécurisation
                if isinstance(extracted[key], list):
                    data[key] = extracted[key]
                else:
                    data[key] = [extracted[key]]
            else:
                data[key] = extracted[key]

    # Détection simple des lignes produits
    for line in text.splitlines():
        if re.search(r"\b(CORNIERE|TUBE|PLAT|FER|ECO\-PART)\b", line, re.IGNORECASE):
            data["line_items"].append(line.strip())

    return data, extracted

# ----------- 🚀 Main ----------------
if len(sys.argv) != 2:
    print("Usage: python3 tesseract_runner3.py <chemin_du_fichier_PDF>")
    sys.exit(1)

pdf_path = sys.argv[1]
print("📥 Lecture du fichier :", pdf_path)

# Charger bibliothèque regex
regex_library = load_regex_library()

# Conversion PDF -> images
print("🖼️ Conversion PDF -> PNG...")
images = convert_from_path(pdf_path)

pages_output = []

for i, img in enumerate(images, start=1):
    print(f"🔎 OCR avec Tesseract sur page {i}...")
    raw_text = pytesseract.image_to_string(img, lang="fra")

    structured, extracted = parse_invoice_text(raw_text, regex_library)
    pages_output.append({
        "page": i,
        "content": raw_text,
        "parsed": structured
    })

    # Mettre à jour bibliothèque si besoin
    regex_library = update_library(regex_library, extracted)

# Sauvegarder la bibliothèque enrichie
save_regex_library(regex_library)

print("✅ OCR terminé")
print(json.dumps({"pages": pages_output}, ensure_ascii=False, indent=2))
