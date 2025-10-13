# -*- coding: utf-8 -*-
import sys
import json
import logging
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import re

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

def load_model(model_file):
    with open(model_file, "r", encoding="utf-8") as f:
        return json.load(f)

def ocr_zone(image, box, original_size):
    img_w, img_h = image.size
    orig_w, orig_h = original_size
    x_px = int((box["x"] / 100) * img_w)
    y_px = int((box["y"] / 100) * img_h)
    w_px = int((box["width"] / 100) * img_w)
    h_px = int((box["height"] / 100) * img_h)
    cropped = image.crop((x_px, y_px, x_px + w_px, y_px + h_px))
    text = pytesseract.image_to_string(cropped, lang="fra")
    return text.strip() if text.strip() else None

def parse_table(text):
    """Découpe un bloc texte en lignes de produits simples"""
    items = []
    for line in text.splitlines():
        m = re.match(r"(\d+)\s+(.*?)\s+([\d.,]+\s?\w*)\s+([\d.,]+)\s+([\d.,]+)", line)
        if m:
            items.append({
                "ref": m.group(1),
                "designation": m.group(2),
                "qty": m.group(3),
                "unit_price": m.group(4),
                "amount": m.group(5),
                "vat": None
            })
    return items

def extract_invoice(pdf_file, model):
    pages = convert_from_path(pdf_file, dpi=300)
    page = pages[0]

    extracted = {}
    line_items = []

    for entry in model:
        zones = entry.get("Document", [])
        for zone in zones:
            labels = zone.get("rectanglelabels", [])
            if not labels:
                continue
            label = labels[0]
            text = ocr_zone(page, zone, (zone["original_width"], zone["original_height"]))
            if label.lower() == "table":
                if text:
                    line_items = parse_table(text)
            else:
                extracted[label] = text if text else None

    extracted["line_items"] = line_items
    return extracted

def main(pdf_file, model_file):
    model = load_model(model_file)
    extracted = extract_invoice(pdf_file, model)

    print("\n=== Résultats JSON ===")
    print(json.dumps(extracted, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python extract_invoice.py <facture.pdf> <modele.json>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
