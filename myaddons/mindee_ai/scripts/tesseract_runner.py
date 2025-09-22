#!/usr/bin/env python3
import sys
import json
import re
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract

# --- Regex génériques ---
INVOICE_PATTERNS = [
    r"facture\s*n[°o]?\s*[:\-]?\s*([A-Za-z0-9\-_/]+)",  # "FACTURE N° 153880"
    r"invoice\s*n[°o]?\s*[:\-]?\s*([A-Za-z0-9\-_/]+)",
]
DATE_PATTERNS = [
    r"\b\d{2}[/-]\d{2}[/-]\d{4}\b",  # 00/00/0000 ou 00-00-0000
]

def extract_phrases(text):
    """Découpe le texte brut en phrases nettoyées"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines

def parse_invoice_data(phrases):
    """Cherche numéro de facture et date"""
    invoice_number = None
    invoice_date = None

    for phrase in phrases:
        lower_phrase = phrase.lower()

        # Numéro de facture
        if not invoice_number:
            for pat in INVOICE_PATTERNS:
                match = re.search(pat, lower_phrase, re.IGNORECASE)
                if match:
                    invoice_number = match.group(1).strip()
                    break

        # Date
        if not invoice_date:
            for pat in DATE_PATTERNS:
                match = re.search(pat, phrase)
                if match:
                    invoice_date = match.group(0)
                    break

    return {"invoice_number": invoice_number, "invoice_date": invoice_date}

def run_ocr(pdf_path: Path):
    """OCR complet sur un PDF"""
    pages = convert_from_path(str(pdf_path))
    results = []

    for idx, page in enumerate(pages, start=1):
        text = pytesseract.image_to_string(page, lang="fra")
        phrases = extract_phrases(text)
        parsed = parse_invoice_data(phrases)

        results.append({
            "page": idx,
            "content": text,
            "phrases": phrases,
            "parsed": parsed,
        })

    return {"pages": results}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    result = run_ocr(pdf_path)

    # 👉 On sort uniquement du JSON
    print(json.dumps(result, ensure_ascii=False, indent=2))
