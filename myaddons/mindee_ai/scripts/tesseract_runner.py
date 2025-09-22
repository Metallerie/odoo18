import sys
import os
import json
import re
import tempfile
from pdf2image import convert_from_path
import pytesseract

# ---------- 🔧 Fonctions utilitaires ----------------

def merge_invoice_number_phrases(phrases):
    """
    Fusionne les phrases du type :
    "Facture d'acompte n°" + "2025/1680" → "Facture d'acompte n° 2025/1680"
    """
    merged = []
    skip_next = False
    invoice_keywords = ["facture", "facture d'acompte", "facture n°", "facture d’acompte"]

    for i, phrase in enumerate(phrases):
        if skip_next:
            skip_next = False
            continue

        lower_phrase = phrase.lower()

        # Détecte une ligne contenant "facture"
        if any(k in lower_phrase for k in invoice_keywords) and i + 1 < len(phrases):
            next_phrase = phrases[i + 1].strip()

            # Vérifie si la ligne suivante ressemble à un numéro de facture
            if re.match(r"^[A-Za-z0-9/\-]+$", next_phrase):
                merged_phrase = f"{phrase.strip()} {next_phrase}"
                merged.append(merged_phrase)
                skip_next = True
                continue

        merged.append(phrase)

    return merged


def extract_invoice_data(phrases):
    """
    Extrait les données principales (n° facture, date) à partir des phrases
    """
    data = {}

    # Regex génériques
    invoice_patterns = [
        r"facture\s*(?:d['’]acompte)?\s*[n°:\-]?\s*([A-Za-z0-9/\-]+)",
    ]
    date_patterns = [
        r"(\d{2}[/-]\d{2}[/-]\d{4})",  # 17/09/2025 ou 17-09-2025
    ]

    for phrase in phrases:
        # Numéro de facture
        for pat in invoice_patterns:
            m = re.search(pat, phrase, flags=re.IGNORECASE)
            if m:
                data["invoice_number"] = m.group(1)
                break

        # Date
        for pat in date_patterns:
            m = re.search(pat, phrase)
            if m:
                data["invoice_date"] = m.group(1)
                break

    return data


# ---------- 🔧 OCR principal ----------------

def run_ocr(pdf_path):
    pages_data = []
    images = convert_from_path(pdf_path)

    for idx, img in enumerate(images, start=1):
        text = pytesseract.image_to_string(img, lang="fra")

        # Découpe en phrases (par ligne)
        phrases = [p.strip() for p in text.split("\n") if p.strip()]

        # Fusionne si besoin (ex: Facture + numéro séparé)
        phrases = merge_invoice_number_phrases(phrases)

        # Extraction
        parsed = extract_invoice_data(phrases)

        pages_data.append({
            "page": idx,
            "content": text,
            "phrases": phrases,
            "parsed": parsed
        })

    return {"pages": pages_data}


# ---------- 🔧 Exécution CLI ----------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tesseract_runner.py <pdf_file>")
        sys.exit(1)

    pdf_file = sys.argv[1]

    if not os.path.exists(pdf_file):
        print(json.dumps({"error": f"File not found: {pdf_file}"}))
        sys.exit(1)

    try:
        result = run_ocr(pdf_file)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
