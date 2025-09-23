#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os, json
from pdf2image import convert_from_path
import pytesseract

def run(pdf_path):
    pages = []
    images = convert_from_path(pdf_path)
    for idx, img in enumerate(images, start=1):
        # OCR texte brut
        text = pytesseract.image_to_string(img, lang="fra")
        phrases = [line.strip() for line in text.split("\n") if line.strip()]

        # Dummy parsing pour vérifier que tout marche
        pages.append({
            "page": idx,
            "content": text[:200] + "...",   # juste un extrait pour debug
            "phrases_count": len(phrases),
            "phrases_sample": phrases[:5]    # les 5 premières lignes
        })
    return {"pages": pages}

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
