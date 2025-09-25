#!/usr/bin/env python3
import sys
import pytesseract
from pytesseract import Output
from pdf2image import convert_from_path
import json

def ocr_with_structure(pdf_path):
    # Convertir PDF -> images
    pages = convert_from_path(pdf_path)
    results = []

    for page_num, page in enumerate(pages, start=1):
        # OCR en mode TSV (avec bbox)
        data = pytesseract.image_to_data(page, output_type=Output.DICT, lang="fra")

        # Découpage zones (simple règle: top 25%, mid 50%, bottom 25%)
        width, height = page.size
        header, body, footer = [], [], []

        for i, text in enumerate(data["text"]):
            if not text.strip():
                continue
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            box = {"text": text, "x": x, "y": y, "w": w, "h": h}

            if y < height * 0.25:
                header.append(box)
            elif y > height * 0.75:
                footer.append(box)
            else:
                body.append(box)

        results.append({
            "page": page_num,
            "header": " ".join([b["text"] for b in header]),
            "body": " ".join([b["text"] for b in body]),
            "footer": " ".join([b["text"] for b in footer]),
            "raw_boxes": {"header": header, "body": body, "footer": footer}
        })

    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 tesseract_runner4.py <fichier.pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"📥 Lecture du fichier : {pdf_path}")

    structured = ocr_with_structure(pdf_path)

    print("✅ OCR structuré terminé")
    print(json.dumps(structured, indent=2, ensure_ascii=False))
