from doctr.models import ocr_predictor
from doctr.io import DocumentFile
import sys
import json

def group_words_into_lines(predictions, y_thresh=0.01):
    lines = []
    for word in sorted(predictions, key=lambda x: (x['bbox'][0][1] + x['bbox'][1][1]) / 2):
        cy = (word['bbox'][0][1] + word['bbox'][1][1]) / 2
        placed = False
        for line in lines:
            ly = (line[0]['bbox'][0][1] + line[0]['bbox'][1][1]) / 2
            if abs(ly - cy) <= y_thresh:
                line.append(word)
                placed = True
                break
        if not placed:
            lines.append([word])
    return lines

def line_to_phrase(line):
    # Fusionne les mots d'une ligne en une phrase
    line = sorted(line, key=lambda x: x['bbox'][0][0])
    phrase = " ".join([word['value'] for word in line])
    return phrase

def possible_product_line(line):
    # Heuristique simple : au moins un nombre et un prix
    words = [w['value'] for w in line]
    has_number = any(w.replace('.', '', 1).isdigit() for w in words)
    has_price = any("," in w or "." in w for w in words)
    # On exclue les lignes d'entête et de total
    exclude = ["Réf.", "Désignation", "Qté", "Unité", "Montant", "TVA", "TOTAL", "Base HT", "FRAIS FIXES", "NET A PAYER", "T.V.A."]
    if any(w in exclude for w in words):
        return False
    return has_number and has_price and len(words) >= 3

def extract_product_lines(lines):
    produits = []
    for line in lines:
        if possible_product_line(line):
            # On essaie de deviner les colonnes (très basique : on prend tous les mots)
            produit = {"ligne": [w['value'] for w in sorted(line, key=lambda x: x['bbox'][0][0])]}
            produits.append(produit)
    return produits

if len(sys.argv) != 2:
    print("Usage: python3 kie_predictor.py <chemin_du_fichier_PDF>")
    sys.exit(1)

pdf_path = sys.argv[1]

print("📥 Lecture du fichier :", pdf_path)
doc = DocumentFile.from_pdf(pdf_path)

print("📚 Chargement du modèle Doctr...")
model = ocr_predictor(pretrained=True)

print("🔎 Prédiction OCR en cours...")
result = model(doc)

predictions = []
for page in result.pages:
    for block in page.blocks:
        for line in block.lines:
            for word in line.words:
                predictions.append({
                    'value': word.value,
                    'bbox': word.geometry,
                })

lines = group_words_into_lines(predictions, y_thresh=0.01)
phrases = [line_to_phrase(line) for line in lines]
produits = extract_product_lines(lines)

print(json.dumps({
    "phrases": phrases,
    "produits": produits
}, ensure_ascii=False, indent=2))
