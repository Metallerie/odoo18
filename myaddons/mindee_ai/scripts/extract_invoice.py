# -*- coding: utf-8 -*-
import sys
import json
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

def load_model(model_path):
    """Charge le fichier JSON complet Label Studio"""
    with open(model_path, "r", encoding="utf-8") as f:
        return json.load(f)

def ocr_zone(img, box, page_w, page_h):
    """
    Extrait le texte d'une zone définie par Label Studio (x,y,width,height en %).
    """
    x = int((box["x"] / 100) * page_w)
    y = int((box["y"] / 100) * page_h)
    w = int((box["width"] / 100) * page_w)
    h = int((box["height"] / 100) * page_h)

    cropped = img.crop((x, y, x + w, y + h))
    text = pytesseract.image_to_string(cropped, lang="fra").strip()
    return text

def extract_with_model(pdf_path, model):
    """Applique OCR sur PDF et récupère les valeurs définies par le modèle JSON"""
    result = {"header": {}, "lines": []}

    images = convert_from_path(pdf_path)
    annotations = model.get("annotations", [])
    if not annotations:
        return result

    for img in images:
        page_w, page_h = img.size

        for item in annotations[0].get("result", []):
            value = item.get("value", {})

            if "rectanglelabels" in value and value["rectanglelabels"]:
                label = value["rectanglelabels"][0]

                # OCR de la zone
                extracted_text = ocr_zone(img, value, page_w, page_h)

                if extracted_text:
                    if label not in ["Reference", "Description", "Quantity", "Unit Price", "Amount HT", "VAT", "Unité"]:
                        result["header"][label] = extracted_text
                    else:
                        result["lines"].append({label: extracted_text})

    return result

def save_json(output_path, data):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Extraction sauvegardée dans {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("⚠️ Usage: python3 extract_invoice.py <facture.pdf> <modele.json> <output.json>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    model_file = sys.argv[2]
    output_file = sys.argv[3]

    model = load_model(model_file)
    extracted = extract_with_model(pdf_file, model)
    save_json(output_file, extracted)
