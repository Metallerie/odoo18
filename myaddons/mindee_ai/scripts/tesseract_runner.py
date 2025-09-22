#!/usr/bin/env python3
import sys
import json
import tempfile
import os
from pdf2image import convert_from_path
import pytesseract
import re

# ---------- 🔑 Extraction générique du numéro de facture ----------
def extract_invoice_number(phrases):
    triggers = ["facture", "facture n°", "facture no", "invoice", "inv."]
    invoice_number = None

    for i, phrase in enumerate(phrases):
        low = phrase.lower()

        # Vérifie si un déclencheur est présent
        if any(t in low for t in triggers):
            # 1. Cherche directement après "facture"
            match = re.search(r"(?:facture\s*(?:n[°o])?\s*[:\-]?\s*)([A-Za-z0-9\-_]+)", phrase, re.IGNORECASE)
            if match:
                invoice_number = match.group(1)
                break

            # 2. Sinon regarde la phrase suivante
            if i + 1 < len(phrases):
                next_phrase = phrases[i + 1].strip()
                if re.match(r"^[A-Za-z0-9\-_]+$", next_phrase):
                    invoice_number = next_phrase
                    break

    return invoice_number


# ---------- 🔑 Extraction générique de la date ----------
def extract_invoice_date(phrases):
    date_pattern = r"\b(\d{2}[\/\-.]\d{2}[\/\-.]\d{4})\b"
    invoice_date = None

    for phrase in phrases:
        low = phrase.lower()
        if "date" in low or "invoice date" in low or "date facture" in low:
            match = re.search(date_pattern, phrase)
            if match:
                invoice_date = match.group(1)
                break

    return invoice_date


# ---------- 🚀 Script principal ----------
def main():
    if len(sys.argv) != 2:
        print("Usage: python3 tesseract_runner.py <fichier.pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"📥 Lecture du fichier : {pdf_path}")

    # Conversion PDF -> images temporaires
    print("🖼️ Conversion PDF -> PNG...")
    pages = convert_from_path(pdf_path)

    results = {"pages": []}

    for idx, page in enumerate(pages, start=1):
        print(f"🔎 OCR avec Tesseract sur page {idx}...")
        text = pytesseract.image_to_string(page, lang="fra")

        # Sépare en phrases (une par ligne)
        phrases = [line.strip() for line in text.splitlines() if line.strip()]

        parsed = {
            "invoice_number": extract_invoice_number(phrases),
            "invoice_date": extract_invoice_date(phrases),
        }

        results["pages"].append({
            "page": idx,
            "content": text,
            "phrases": phrases,
            "parsed": parsed,
        })

    print("✅ OCR terminé")
    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
