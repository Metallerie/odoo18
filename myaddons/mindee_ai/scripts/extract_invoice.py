# -*- coding: utf-8 -*-
import sys
import json
import logging
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
from prettytable import PrettyTable

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s - %(message)s")

def load_model(model_file):
    logging.info(f"Chargement du modèle JSON : {model_file}")
    with open(model_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    logging.debug(f"JSON chargé : type={type(data)} taille={len(data)}")
    return data

def ocr_zone(image, box, original_size):
    """OCRise une zone définie dans le JSON Label Studio"""
    img_w, img_h = image.size
    orig_w, orig_h = original_size

    # Conversion % -> pixels
    x_px = int((box["x"] / 100) * img_w)
    y_px = int((box["y"] / 100) * img_h)
    w_px = int((box["width"] / 100) * img_w)
    h_px = int((box["height"] / 100) * img_h)

    cropped = image.crop((x_px, y_px, x_px + w_px, y_px + h_px))
    text = pytesseract.image_to_string(cropped, lang="fra")
    return text.strip()

def extract_invoice(pdf_file, model):
    logging.info(f"Conversion du PDF en images : {pdf_file}")
    pages = convert_from_path(pdf_file, dpi=300)
    if not pages:
        logging.error("Aucune page détectée dans le PDF")
        return {}

    page = pages[0]  # pour l’instant on gère une seule page

    results = {}
    for entry in model:
        zones = entry.get("Document", [])
        logging.debug(f"Analyse entrée JSON id={entry.get('id')} avec {len(zones)} zones")
        for zone in zones:
            labels = zone.get("rectanglelabels", [])
            if not labels:
                continue
            label = labels[0]
            text = ocr_zone(page, zone, (zone["original_width"], zone["original_height"]))
            results[label] = text
            logging.debug(f"OCR {label} → {text}")

    return results

def main(pdf_file, model_file):
    model = load_model(model_file)
    extracted = extract_invoice(pdf_file, model)

    print("\n=== Résultats OCR par champ ===")
    table = PrettyTable(["Champ", "Valeur OCR"])
    for champ, valeur in extracted.items():
        table.add_row([champ, valeur])
    print(table)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python extract_invoice.py <facture.pdf> <modele.json>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    model_file = sys.argv[2]
    main(pdf_file, model_file)
