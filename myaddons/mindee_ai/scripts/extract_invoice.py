# -*- coding: utf-8 -*-
import json
import sys
import logging
from pdf2image import convert_from_path
from PIL import Image
import pytesseract

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s - %(message)s")

def load_model(model_file):
    """Charge le modèle JSON"""
    with open(model_file, "r", encoding="utf-8") as f:
        return json.load(f)

def ocr_crop(image, bbox):
    """OCR sur une zone de l'image définie par bbox = [x, y, width, height]"""
    x, y, w, h = bbox
    crop = image.crop((x, y, x + w, y + h))
    text = pytesseract.image_to_string(crop, lang="fra")
    logging.debug(f"OCR zone {bbox} → {text.strip()}")
    return text.strip()

def extract_invoice(pdf_file, model):
    """Extrait les champs en fonction des zones définies dans le JSON"""
    results = {}

    # Convertir le PDF en images (une page)
    pages = convert_from_path(pdf_file, dpi=300)
    page = pages[0]  # on prend la première page pour l’instant

    for field in model:
        field_name = field.get("name")
        bbox = field.get("bbox")  # attendu: [x, y, width, height]

        if not bbox or not field_name:
            continue

        value = ocr_crop(page, bbox)
        results[field_name] = value

    return results

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_invoice.py <pdf_file> <model.json>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    model_file = sys.argv[2]

    model = load_model(model_file)
    extracted = extract_invoice(pdf_file, model)

    print("\n=== Résultats OCR par champ ===")
    for k, v in extracted.items():
        print(f"{k:20} : {v}")
