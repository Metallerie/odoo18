# -*- coding: utf-8 -*-
"""
Lecture d'un export Label Studio (mini) et affichage en console
Usage:
  python3 parse_labelstudio.py <fichier.json>
"""
import sys
import json
from prettytable import PrettyTable

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_labelstudio(data):
    """
    Parse un JSON mini exporté de Label Studio
    Retourne un dict {champ: valeur}
    """
    results = {}

    # On va chercher dans annotations -> result
    for ann in data.get("annotations", []):
        for item in ann.get("result", []):
            value = item.get("value", {})

            # Champs header (label + valeur)
            if "header_label" in value and "header_value" in value:
                label = " ".join(value["header_label"])
                val = " ".join(value["header_value"])
                results[label] = val

            # Footer
            if "footer_label" in value and "footer_value" in value:
                label = " ".join(value["footer_label"])
                val = " ".join(value["footer_value"])
                results[label] = val

            # Lignes de tableau (simplification)
            if "line_cells" in value and "line_value" in value:
                label = " | ".join(value["line_cells"])
                val = " ".join(value["line_value"])
                results[label] = val

    return results

def display_table(results):
    table = PrettyTable()
    table.field_names = ["Champ", "Valeur"]

    for k, v in results.items():
        table.add_row([k, v])

    print(table)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 parse_labelstudio.py <fichier.json>")
        sys.exit(1)

    json_file = sys.argv[1]
    data = load_json(json_file)
    results = parse_labelstudio(data)

    if results:
        display_table(results)
    else:
        print("⚠️ Aucun champ trouvé dans ce fichier.")
