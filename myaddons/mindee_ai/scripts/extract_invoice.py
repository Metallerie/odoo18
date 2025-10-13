# /data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/scripts/extract_invoice.py
import sys
import json
import logging
import pdfplumber
from prettytable import PrettyTable

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s - %(message)s")

def load_model(model_path):
    """Charge le modèle JSON du fournisseur"""
    with open(model_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logging.info(f"Type JSON chargé: {type(data)}")
    if isinstance(data, list):
        logging.info(f"Liste avec {len(data)} éléments, on prend le premier")
        return data[0]
    return data

def extract_invoice(pdf_path, model):
    """Extrait les infos de la facture selon le modèle"""
    results = []

    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    logging.debug(f"Texte extrait du PDF ({len(full_text)} caractères)")

    # On cherche la clé annotations/result
    annotations = []
    if "annotations" in model:
        anns = model["annotations"]
        if anns and "result" in anns[0]:
            annotations = anns[0]["result"]

    logging.info(f"{len(annotations)} annotations trouvées dans le modèle")

    for ann in annotations:
        value = ann.get("value", {})
        label_list = value.get("labels", [])
        label = label_list[0] if label_list else "inconnu"
        text_list = value.get("text", [])
        text = text_list[0] if text_list else ""
        logging.debug(f"Annotation: {label} → '{text}'")

        if text and text in full_text:
            logging.debug(f"✔ Match trouvé pour '{label}' : {text}")
            results.append((label, text))
        else:
            logging.warning(f"❌ Pas trouvé : {label} ({text})")

    return results

def main(pdf_file, model_file):
    logging.info(f"📄 Lecture facture : {pdf_file}")
    logging.info(f"📦 Modèle fournisseur : {model_file}")

    model = load_model(model_file)
    if not model:
        print("⚠️ Modèle JSON vide ou incorrect")
        return

    extracted = extract_invoice(pdf_file, model)

    table = PrettyTable()
    table.field_names = ["Champ", "Valeur OCR"]
    for label, value in extracted:
        table.add_row([label, value])
    print(table)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_invoice.py <fichier.pdf> <modele.json>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
