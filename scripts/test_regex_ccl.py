import re
import json

# Charger la bibliothèque regex CCL
with open("regex_ccl.json", "r", encoding="utf-8") as f:
    regex_lib = json.load(f)["CCL"]

# Charger le texte OCR (extrait de Tesseract)
with open("facture_ccl_ocr.txt", "r", encoding="utf-8") as f:
    text = f.read()

results = {}

# Tester chaque regex
for key, item in regex_lib.items():
    pattern = re.compile(item["pattern"])
    matches = pattern.findall(text)

    if matches:
        results[key] = matches
    else:
        results[key] = None

# Afficher résultats
print("=== Résultats extraction Regex CCL ===")
for field, value in results.items():
    print(f"{field}: {value}")
