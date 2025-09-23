#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os, json, re
from pdf2image import convert_from_path
import pytesseract

# ---------------- Détection des zones ----------------
HEADER_KEYWORDS = [
    "réf", "reference", "code",
    "désign", "article", "produit",
    "qté", "quantité",
    "unité", "poids",
    "prix", "pu", "unitaire",
    "montant", "total",
    "tva"
]

FOOT_RE = re.compile(r"total|net\s*[àa]\s*payer|base\s*ht", re.I)

def is_header_line(line: str) -> bool:
    """Détecte une ligne d'entête si au moins 2 mots-clés sont présents."""
    l = line.lower()
    hits = sum(1 for k in HEADER_KEYWORDS if k in l)
    return hits >= 2

def run(pdf_path):
    pages = []
    images = convert_from_path(pdf_path)

    for idx, img in enumerate(images, start=1):
        text = pytesseract.image_to_string(img, lang="fra")
        phrases = [p.strip() for p in text.split("\n") if p.strip()]

        # Cherche l'entête élargie
        header_i = None
        for i, ph in enumerate(phrases):
            if is_header_line(ph):
                header_i = i
                break

        footer_i = None
        if header_i is not None:
            for j in range(header_i + 1, len(phrases)):
                if FOOT_RE.search(phrases[j]):
                    footer_i = j
                    break

        # Construction des zones
        if header_i is not None:
            headers = phrases[header_i].split()
            table_lines = phrases[header_i + 1:footer_i] if footer_i else phrases[header_i + 1:]
            normal_before = phrases[:header_i]
            normal_after = phrases[footer_i:] if footer_i else []
        else:
            headers = []
            table_lines = []
            normal_before = phrases
            normal_after = []

        pages.append({
            "page": idx,
            "normal_phrases": normal_before + normal_after,
            "table": {
                "headers": headers,
                "lines": table_lines
            }
        })

    return {"pages": pages}


# ---------------- CLI ----------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Usage: python3 tesseract_runner2.py <file.pdf>")
        sys.exit(1)

    pdf = sys.argv[1]
    if not os.path.exists(pdf):
        print(json.dumps({"error": f"file not found: {pdf}"}))
        sys.exit(1)

    try:
        data = run(pdf)
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
