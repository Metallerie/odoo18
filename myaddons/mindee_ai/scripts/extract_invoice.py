# -*- coding: utf-8 -*-
import sys
import json
import pytesseract
from pdf2image import convert_from_path

def load_model(model_path):
    with open(model_path, "r", encoding="utf-8") as f:
        return json.load(f)

def ocr_pdf(pdf_path):
    """Convertit le PDF en image(s) puis applique Tesseract OCR"""
    images = convert_from_path(pdf_path)
    text_results = []
    for i, img in enumerate(images):
        text = pytesseract.image_to_string(img, lang="fra")
        text_results.append({"page": i+1, "text": text})
    return text_results

def extract_with_model(ocr_text, model):
    """
    Associe les positions / labels du modèle aux valeurs détectées par OCR.
    Ici on simplifie : on cherche juste les mots-clés (Invoice Number, Date...).
    """
    result = {"header": {}, "lines": []}

    for annotation in model.get("annotations", []):
        for item in annotation.get("result", []):
            label = None
            if "rectanglelabels" in item["value"]:
                label = item["value"]["rectanglelabels"][0]

            if label:
                # 🔎 Ici simplification : on recherche le label dans le texte OCR
                found = None
                for page in ocr_text:
                    if label.lower() in page["text"].lower():
                        found = page["text"]
                        break
                result["header"][label] = found if found else "NON TROUVÉ"

    return result

def save_json(output_path, data):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("⚠️ Usage: python3 extract_invoice.py <facture.pdf> <modele.json> <output.json>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    model_file = sys.argv[2]
    output_file = sys.argv[3]

    model = load_model(model_file)
    ocr_text = ocr_pdf(pdf_file)
    extracted = extract_with_model(ocr_text, model)
    save_json(output_file, extracted)

    print(f"✅ Extraction terminée → {output_file}")
