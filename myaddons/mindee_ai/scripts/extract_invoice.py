# -*- coding: utf-8 -*-
"""
Extraction des champs d'une facture PDF à partir d'un modèle Label Studio (zones)
Usage :
  python3 extract_invoice.py <facture.pdf> <modele.json>
"""
import sys
import json
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from prettytable import PrettyTable

def load_model(model_path):
    """Charge un modèle JSON fournisseur (Label Studio)"""
    with open(model_path, "r", encoding="utf-8") as f:
        return json.load(f)

def ocr_zone(img, box, page_w, page_h):
    """
    Extrait le texte d'une zone définie par Label Studio (coordonnées en %)
    """
    x = int((box["x"] / 100) * page_w)
    y = int((box["y"] / 100) * page_h)
    w = int((box["width"] / 100) * page_w)
    h = int((box["height"] / 100) * page_h)

    cropped = img.crop((x, y, x + w, y + h))
    text = pytesseract.image_to_string(cropped, lang="fra").strip()
    return text

def extract_invoice(pdf_path, model):
    """Extrait les valeurs OCR du PDF selon les zones du modèle"""
    results = {}
    images = convert_from_path(pdf_path)

    annotations = model.get("annotations", [])
    if not annotations:
        print("⚠️ Modèle JSON vide ou incorrect")
        return results

    for img in images:
        page_w, page_h = img.size

        for item in annotations[0].get("result", []):
            value = item.get("value", {})
            if "rectanglelabels" in value and value["rectanglelabels"]:
                label = value["rectanglelabels"][0]

                extracted_text = ocr_zone(img, value, page_w, page_h)
                if extracted_text:
                    results[label] = extracted_text

    return results

def display_table(results):
    """Affiche les résultats dans un tableau console"""
    table = PrettyTable()
    table.field_names = ["Champ", "Valeur OCR"]

    for label, val in results.items():
        table.add_row([label, val])

    print(table)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("⚠️ Usage: python3 extract_invoice.py <facture.pdf> <modele.json>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    model_file = sys.argv[2]

    model = load_model(model_file)
    extracted = extract_invoice(pdf_file, model)
    display_table(extracted)
