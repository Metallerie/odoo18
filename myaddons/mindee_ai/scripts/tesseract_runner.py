#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json
from pdf2image import convert_from_path
import pytesseract

def run_ocr(pdf_path):
    print(f"🔎 OCR lancé sur : {pdf_path}")

    if not os.path.exists(pdf_path):
        print(f"❌ Fichier introuvable : {pdf_path}")
        return {"error": "file not found"}

    try:
        print("📄 Conversion PDF → images…")
        images = convert_from_path(pdf_path)
        print(f"✅ {len(images)} page(s) détectée(s).")
    except Exception as e:
        print(f"❌ Erreur pdf2image : {e}")
        return {"error": str(e)}

    pages_data = []
    for idx, img in enumerate(images, start=1):
        print(f"🔎 OCR page {idx}…")
        try:
            text = pytesseract.image_to_string(img, lang="fra")
        except Exception as e:
            print(f"❌ Erreur OCR : {e}")
            continue

        phrases = [p.strip() for p in text.split("\n") if p.strip()]
        print(f"✅ {len(phrases)} phrases extraites page {idx}")

        pages_data.append({
            "page": idx,
            "phrases": phrases[:10],  # affiche seulement un extrait
        })

    print("🎉 OCR terminé")
    return {"pages": pages_data}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tesseract_runner.py <pdf_file>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    result = run_ocr(pdf_file)
    print(json.dumps(result, indent=2, ensure_ascii=False))
