from doctr.models import kie_predictor
from doctr.io import DocumentFile
import sys
import json


# ----------- 🔧 Fonctions ----------------

def group_predictions_into_lines(predictions, y_thresh=0.01):
    """Regroupe les prédictions KIE par ligne en fonction de leur coordonnée Y."""
    lines = []
    for pred in sorted(predictions, key=lambda x: (x['bbox'][0][1] + x['bbox'][1][1]) / 2):
        cy = (pred['bbox'][0][1] + pred['bbox'][1][1]) / 2
        placed = False
        for line in lines:
            ly = (line[0]['bbox'][0][1] + line[0]['bbox'][1][1]) / 2
            if abs(ly - cy) <= y_thresh:
                line.append(pred)
                placed = True
                break
        if not placed:
            lines.append([pred])
    return lines


def line_to_phrase(line):
    """Fusionne les prédictions d'une ligne en une phrase lisible"""
    line = sorted(line, key=lambda x: x['bbox'][0][0])  # tri horizontal
    phrase = " ".join([pred['value'] for pred in line if pred['value']])
    return phrase


def possible_product_line(line):
    """Heuristique pour détecter une ligne produit (contient chiffres + prix)"""
    words = [w['value'] for w in line if w['value']]
    has_number = any(w.replace('.', '', 1).isdigit() for w in words)
    has_price = any("," in w or "." in w for w in words)
    exclude = ["Réf.", "Désignation", "Qté", "Unité", "Montant", "TVA",
               "TOTAL", "Base HT", "FRAIS FIXES", "NET A PAYER", "T.V.A."]
    if any(w in exclude for w in words):
        return False
    return has_number and has_price and len(words) >= 3


def extract_product_lines(lines):
    produits = []
    for line in lines:
        if possible_product_line(line):
            produit = {"ligne": [w['value'] for w in sorted(line, key=lambda x: x['bbox'][0][0])]}
            produits.append(produit)
    return produits


# ----------- 🚀 Script principal ----------------

if len(sys.argv) != 2:
    print("Usage: python3 kie_predictor.py <chemin_du_fichier_PDF>")
    sys.exit(1)

pdf_path = sys.argv[1]
print("📥 Lecture du fichier :", pdf_path)

doc = DocumentFile.from_pdf(pdf_path)

print("📚 Chargement du modèle KIE Doctr...")
model = kie_predictor(pretrained=True)

print("🔎 Prédiction KIE en cours...")
result = model(doc)

# 🔎 Extraction des prédictions brutes
predictions = []
for page_idx, page in enumerate(result.pages):
    for pred in page.predictions:
        predictions.append({
            "page": page_idx + 1,
            "label": getattr(pred, "label", None),
            "value": getattr(pred, "value", None),
            "bbox": getattr(pred, "geometry", None),
            "confidence": getattr(pred, "confidence", None),
        })

# ✅ Séparation des prédictions
valid_predictions = [p for p in predictions if p["bbox"] is not None]
invalid_predictions = [p for p in predictions if p["bbox"] is None]

# 📐 Reconstruction des lignes
lines = group_predictions_into_lines(valid_predictions, y_thresh=0.01)
phrases = [line_to_phrase(line) for line in lines]

# 🛒 Extraction des produits
produits = extract_product_lines(lines)

# 📦 Export JSON
output = {
    "phrases": phrases,
    "produits": produits,
    "extractions_valides": valid_predictions,
    "extractions_sans_bbox": invalid_predictions,
}

print(json.dumps(output, ensure_ascii=False, indent=2))
