#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import json
from pdf2image import convert_from_path
import pytesseract

def ocr_with_bbox(pdf_path):
    pages_data = []
    images = convert_from_path(pdf_path)

    for page_num, img in enumerate(images, start=1):
        # OCR mot par mot avec coordonnées
        data = pytesseract.image_to_data(img, lang="fra", output_type=pytesseract.Output.DICT)

        words = []
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            if text:
                words.append({
                    "text": text,
                    "x": data["left"][i],
                    "y": data["top"][i],
                    "w": data["width"][i],
                    "h": data["height"][i],
                })

        # 🔹 Regrouper les mots en lignes par proximité verticale
        lines = []
        current_line = []
        last_y = None

        for w in sorted(words, key=lambda x: (x["y"], x["x"])):
            if last_y is None or abs(w["y"] - last_y) <= 10:  # tolérance verticale
                current_line.append(w)
            else:
                lines.append(current_line)
                current_line = [w]
            last_y = w["y"]

        if current_line:
            lines.append(current_line)

        # 🔹 Reconstituer texte + colonnes
        structured_lines = []
        for line in lines:
            line_sorted = sorted(line, key=lambda x: x["x"])
            structured_lines.append({
                "text": " ".join([w["text"] for w in line_sorted]),
                "words": line_sorted
            })

        pages_data.append({
            "page": page_num,
            "lines": structured_lines
        })

    return {"pages": pages_data}

# ---------------- CLI ----------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tesseract_bbox_runner.py <pdf_file>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    if not os.path.exists(pdf_file):
        print(json.dumps({"error": f"File not found: {pdf_file}"}))
        sys.exit(1)

    result = ocr_with_bbox(pdf_file)
    print(json.dumps(result, indent=2, ensure_ascii=False))
