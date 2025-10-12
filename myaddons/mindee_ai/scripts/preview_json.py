# -*- coding: utf-8 -*-
import sys
import json
from prettytable import PrettyTable

def load_json(file_path):
    """Charge un fichier JSON et le retourne en dict"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Erreur de lecture JSON {file_path}: {e}")
        sys.exit(1)

def extract_fields(data):
    """
    Extrait les champs intéressants du JSON Label Studio enrichi.
    ⚠️ Ici je suppose que tu stockes les valeurs extraites sous 'result'
    et que tu différencies header / table / footer.
    """
    fields = []

    # Parcourir les résultats
    for annotation in data.get("annotations", []):
        for item in annotation.get("result", []):
            label = None
            value = None

            # On récupère le label (ex: Invoice Number, Date, SIREN…)
            if "rectanglelabels" in item["value"]:
                label = item["value"]["rectanglelabels"][0]

            # On récupère la valeur associée (textarea dans ton JSON)
            if "text" in item["value"]:
                value = " ".join(item["value"]["text"])

            if label and value:
                fields.append((label, value))

    return fields

def display_table(fields):
    """Affiche les champs dans un tableau PrettyTable"""
    table = PrettyTable()
    table.field_names = ["Champ", "Valeur OCR", "Valeur validée"]

    for label, value in fields:
        table.add_row([label, value, " "])  # la colonne validée reste vide

    print(table)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("⚠️ Usage: python3 preview_json.py <fichier.json>")
        sys.exit(1)

    json_file = sys.argv[1]
    data = load_json(json_file)
    fields = extract_fields(data)

    if not fields:
        print("❌ Aucun champ trouvé dans ce JSON.")
    else:
        display_table(fields)
