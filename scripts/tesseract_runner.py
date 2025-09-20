import sys
import os
import json
import tempfile
import subprocess

from pdf2image import convert_from_path
import pytesseract

# ----------- 🔧 Fonctions utilitaires ----------------

def parse_invoice_text(text):
    """Parse le texte brut d'une facture en JSON structuré."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    data = {
        "invoice_number": None,
        "invoice_date": None,
        "client": None,
        "products": [],
        "totals": {}
    }

    for line in lines:
        low = line.lower()

        # Numéro facture
        if "facture" in low and ("n" in low or "no" in low or "n°" in low):
            for word in line.split():
                if word.isdigit():
                    data["invoice_number"] = word

        # Date facture
        if "date facture" in low:
            for word in line.split():
                if "/" in word and word.replace("/", "").isdigit():
                    data["invoice_date"] = word

        # Client
        if line.startswith("Client"):
            parts = line.split(":")
            if len(parts) > 1:
                data["client"] = parts[1].strip()

        # Produits (heuristique : contient ref + désignation + quantité + prix)
        if any(x in line for x in ["CORNIERE", "TUBE", "PLAT", "FER"]):
            data["products"].append(line)

        # Totaux
        if "net ht" in low:
            for word in line.replace(",", ".").split():
                if word.replace(".", "").isdigit():
                    data["totals"]["net_ht"] = word
        if "t.v.a" in low or "tva" in low:
            for word in line.replace(",", ".").split():
                if word.replace(".", "").isdigit():
                    data["totals"]["tva"] = word
        if "net a payer" in low:
            for word in line.replace(",", ".").replace("€", "").split():
                if word.replace(".", "").isdigit():
                    data["totals"]["net_a_payer"] = word

    return data


# ----------- 🚀 Script principal ----------------

if len(sys.argv) != 2:
    print("Usage: python3 tesseract_runner.py <chemin_du_fichier_PDF>")
    sys.exit(1)

pdf_path = sys.argv[1]
print("📥 Lecture du fichier :", pdf_path)

# Conversion PDF -> images
print("🖼️ Conversion PDF -> PNG...")
images = convert_from_path(pdf_path)

pages_output = []

for i, img in enumerate(images, start=1):
    print(f"🔎 OCR avec Tesseract sur page {i}...")
    raw_text = pytesseract.image_to_string(img, lang="fra")
    structured = parse_invoice_text(raw_text)

    pages_output.append({
        "page": i,
        "content": raw_text,
        "parsed": structured
    })

print("✅ OCR terminé")
print(json.dumps({"pages": pages_output}, ensure_ascii=False, indent=2))
