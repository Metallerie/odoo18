# extract_invoice.py
# -*- coding: utf-8 -*-
import sys
import ijson
import demjson3
import pdfplumber
from prettytable import PrettyTable

def load_model(model_path):
    with open(model_path, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read()
    return demjson3.decode(raw)


def extract_text(pdf_file):
    """OCR simple avec pdfplumber (texte brut)"""
    text = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text.append(page.extract_text() or "")
    return "\n".join(text)

def main(pdf_file, model_file):
    print(f"📄 Lecture facture : {pdf_file}")
    print(f"📦 Modèle fournisseur : {model_file}")

    model = load_model(model_file)
    text = extract_text(pdf_file)

    table = PrettyTable(["Champ", "Position (x,y)", "Valeur trouvée"])
    for field in model:
        value = "🔍 à implémenter (regex ou zone OCR)"
        table.add_row([field["label"], f"({field['x']},{field['y']})", value])

    print(table)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 extract_invoice.py <facture.pdf> <modele.json>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    model_file = sys.argv[2]
    main(pdf_file, model_file)
