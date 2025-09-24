import sys
import os
import json
import re
from datetime import datetime
from pdf2image import convert_from_path
import pytesseract

# Charger la librairie regex CCL
from mindee_ai.regex.ccl_regex import ccl_regex


def normalize_amount(val):
    """Nettoie un montant : supprime espaces, €, remplace virgule par point"""
    val = val.replace("€", "").replace(" ", "").replace(",", ".")
    try:
        return float(val)
    except:
        return val


def apply_regex(text, regex_dict):
    """Applique les regex définies dans la bibliothèque."""
    results = {"line_items": []}

    for field, data in regex_dict["fields"].items():
        # Cas spécial : line_item
        if field == "line_item":
            regex = re.compile(data["patterns"][0]["regex"])
            matches = regex.findall(text)
            results["line_items"] = [" ".join(m) if isinstance(m, tuple) else m for m in matches]
            continue

        # Champs institutionnels → comparer tous les patterns
        found = None
        for pattern in data["patterns"]:
            regex = re.compile(pattern["regex"])
            match = regex.search(text)
            if match:
                found = match.group(1) if match.groups() else match.group(0)
                break
        results[field] = found

    return results


def update_library(field, new_regex):
    """Ajoute un nouveau regex dans la bibliothèque si nécessaire (hors line_item)."""
    global ccl_regex
    if field == "line_item":
        return  # on n'évolue pas les regex produits

    patterns = ccl_regex["fields"][field]["patterns"]

    # Vérifier si déjà présent
    for p in patterns:
        if p["regex"] == new_regex:
            return

    new_id = str(len(patterns) + 1)
    patterns.append({"id": new_id, "regex": new_regex, "validated": False})
    ccl_regex["meta"]["update_count"] += 1
    ccl_regex["meta"]["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Sauvegarde dans le fichier
    with open("myaddons/mindee_ai/regex/ccl_regex.py", "w", encoding="utf-8") as f:
        f.write("ccl_regex = " + json.dumps(ccl_regex, indent=2, ensure_ascii=False))


# ----------- 🚀 Script principal ----------------

if len(sys.argv) != 2:
    print("Usage: python3 tesseract_runner3.py <chemin_du_fichier_PDF>")
    sys.exit(1)

pdf_path = sys.argv[1]
print("📥 Lecture du fichier :", pdf_path)

# Conversion PDF -> images
print("🖼️ Conversion PDF -> PNG...")
images = convert_from_path(pdf_path)

pages_output = []
custom_config = r'--psm 6'

for i, img in enumerate(images, start=1):
    print(f"🔎 OCR avec Tesseract sur page {i}...")
    raw_text = pytesseract.image_to_string(img, lang="fra", config=custom_config)

    extracted = apply_regex(raw_text, ccl_regex)

    pages_output.append({
        "page": i,
        "content": raw_text,
        "parsed": extracted
    })

print("✅ OCR terminé")
print(json.dumps({"pages": pages_output}, ensure_ascii=False, indent=2))
