# extract_invoice_simple.py

import sys
import json
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

def ocr_from_pdf(pdf_file, x, y, w, h):
    """Extrait texte OCR d'une case (x,y,w,h en %) depuis un PDF."""
    doc = fitz.open(pdf_file)
    page = doc[0]  # première page
    pix = page.get_pixmap()
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    # Conversion % → coordonnées absolues
    abs_x = int(x / 100 * img.width)
    abs_y = int(y / 100 * img.height)
    abs_w = int(w / 100 * img.width)
    abs_h = int(h / 100 * img.height)

    # Découpe l'image
    crop = img.crop((abs_x, abs_y, abs_x + abs_w, abs_y + abs_h))

    # OCR
    text = pytesseract.image_to_string(crop, lang="fra")
    return text.strip() if text.strip() else "NUL"

def main(pdf_file, json_file):
    with open(json_file, "r", encoding="utf-8") as f:
        model = json.load(f)

    print("=== Cases détectées avec OCR ===")
    for entry in model:
        for zone in entry.get("annotations", [])[0].get("result", []):
            label_list = zone["value"].get("rectanglelabels", [])
            label = label_list[0] if label_list else "NUL"

            x, y = zone["value"]["x"], zone["value"]["y"]
            w, h = zone["value"]["width"], zone["value"]["height"]

            ocr_text = ocr_from_pdf(pdf_file, x, y, w, h)
            print(f"[Case] {label} → {ocr_text}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_invoice_simple.py <facture.pdf> <modele.json>")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
