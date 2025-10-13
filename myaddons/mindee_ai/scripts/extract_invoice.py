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
    results = []

    # Texte du PDF
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    logging.debug(f"Texte extrait du PDF ({len(full_text)} caractères)")

    annotations = []
    if isinstance(model, list):
        for entry in model:
            anns = entry.get("annotations", [])
            for ann in anns:
                for res in ann.get("result", []):
                    annotations.append(res)

    logging.info(f"{len(annotations)} champs trouvés dans le modèle")

    for ann in annotations:
        value = ann.get("value", {})
        labels = value.get("labels", ["inconnu"])
        label = labels[0] if labels else "inconnu"

        # Recherche dans le texte PDF
        found = None
        if label == "invoice_number":
            match = re.search(r"FACTURE\s*[:N°]*\s*(\d+)", full_text, re.IGNORECASE)
            if match:
                found = match.group(1)

        elif label == "invoice_date":
            match = re.search(r"Date\s*facture\s*[:]*\s*(\d{2}/\d{2}/\d{4})", full_text, re.IGNORECASE)
            if match:
                found = match.group(1)

        results.append((label, found or "❌ non trouvé"))

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
