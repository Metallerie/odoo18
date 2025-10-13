import json
import re
import sys
import logging
import pdfplumber
from prettytable import PrettyTable

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s - %(message)s")


def load_model(model_file):
    with open(model_file, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_invoice(pdf_path, model):
    results = []

    # 🔎 Extraction du texte PDF
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    logging.debug(f"Texte extrait du PDF ({len(full_text)} caractères)")

    # 🔎 On prend toutes les cases définies dans le modèle
    labels = []
    if isinstance(model, list):
        for entry in model:
            anns = entry.get("annotations", [])
            for ann in anns:
                for res in ann.get("result", []):
                    val = res.get("value", {})
                    labs = val.get("labels", [])
                    for l in labs:
                        labels.append(l)

    logging.info(f"{len(labels)} champs trouvés dans le modèle")

    # 🔎 Recherche des valeurs dans le texte PDF
    for label in labels:
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
    model = load_model(model_file)
    extracted = extract_invoice(pdf_file, model)

    table = PrettyTable(["Champ", "Valeur OCR"])
    for label, value in extracted:
        table.add_row([label, value])

    print(table)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_invoice.py <facture.pdf> <modele.json>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    model_file = sys.argv[2]
    main(pdf_file, model_file)
