#!/usr/bin/env python3
import sys
import os
import pytesseract
from pdf2image import convert_from_path
import re
import json

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
    "../odoo18/myaddons/mindee_ai/regex/ccl_regex.json"
)
with open(regex_file, "r", encoding="utf-8") as f:
    regex_patterns = json.load(f)

def parse_text(text):
    """Extrait les champs via regex JSON"""
    parsed = {}
    for key, pattern in regex_patterns.items():
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            parsed[key] = match.group(1).strip()
    return parsed

# --- OCR et parsing ---
for i, img in enumerate(images, start=1):
    text = pytesseract.image_to_string(img, lang="fra")
    parsed = parse_text(text)
    results.append({
        "page": i,
        "parsed": parsed
    })

# --- Réorganisation en zones ---
def format_parsed(parsed):
    return {
        "header": {
            "invoice_number": parsed.get("invoice_number"),
            "invoice_date": parsed.get("invoice_date"),
            "client_id": parsed.get("client_id"),
            "client_name": parsed.get("client_name"),
            "siren": parsed.get("siren"),
            "fournisseur": parsed.get("fournisseur"),
        },
        "body": {
            "total_ht": parsed.get("total_ht"),
            "total_tva": parsed.get("total_tva"),
        },
        "footer": {
            "total_ttc": parsed.get("total_ttc"),
            "iban": parsed.get("iban"),
            "bic": parsed.get("bic"),
        }
    }

# --- Affichage final ---
print("✅ OCR + parsing terminé")
print(json.dumps(results, indent=2, ensure_ascii=False))

print("\n🗂️ Données réorganisées en zones")
for page in results:
    parsed = page.get("parsed", {})
    formatted = format_parsed(parsed)
    print(json.dumps(formatted, indent=2, ensure_ascii=False))
