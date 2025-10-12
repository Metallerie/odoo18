# -*- coding: utf-8 -*-
import sys
import json

def load_model(model_path):
    """Charge le fichier JSON complet Label Studio"""
    try:
        with open(model_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Erreur lecture JSON {model_path}: {e}")
        sys.exit(1)

def extract_with_model(model):
    """
    Lis un export Label Studio complet et récupère les labels + valeurs OCR associées
    """
    result = {"header": {}, "lines": []}

    annotations = model.get("annotations", [])
    if not annotations:
        print("⚠️ Aucun bloc annotations trouvé dans ce JSON.")
        return result

    for item in annotations[0].get("result", []):
        value = item.get("value", {})

        # Label (ex: Invoice Number, Date, Client…)
        label = None
        if "rectanglelabels" in value and value["rectanglelabels"]:
            label = value["rectanglelabels"][0]

        # Valeur associée (ex: 163908, 07/10/2025…)
        text = None
        if "text" in value and value["text"]:
            text = " ".join(value["text"])

        if label and text:
            # Cas Header (infos générales)
            if label not in ["Reference", "Description", "Quantity", "Unit Price", "Amount HT", "VAT", "Unité"]:
                result["header"][label] = text
            else:
                # Cas Lignes (tableau facture)
                result["lines"].append({label: text})

    return result

def save_json(output_path, data):
    """Sauvegarde le JSON résultat"""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ Extraction sauvegardée dans {output_path}")
    except Exception as e:
        print(f"❌ Erreur sauvegarde {output_path}: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("⚠️ Usage: python3 extract_invoice.py <modele.json> <output.json>")
        sys.exit(1)

    model_file = sys.argv[1]
    output_file = sys.argv[2]

    model = load_model(model_file)
    extracted = extract_with_model(model)
    save_json(output_file, extracted)
