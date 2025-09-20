# scripts/kie_predictor.py

from doctr.models import kie_predictor
from doctr.io import DocumentFile
import sys
import re

# ------------------- GROUPER PHRASES ------------------- #

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

def merge_words_in_line(line, x_gap_thresh=0.02):
    line = sorted(line, key=lambda x: x['bbox'][0][0])
    sentence = []
    current_phrase = line[0]['value']
    for i in range(1, len(line)):
        prev_right = line[i-1]['bbox'][1][0]
        cur_left = line[i]['bbox'][0][0]
        gap = cur_left - prev_right
        if gap < x_gap_thresh:
            current_phrase += ' ' + line[i]['value']
        else:
            sentence.append(current_phrase)
            current_phrase = line[i]['value']
    sentence.append(current_phrase)
    return sentence

def print_ocr_sentences(predictions):
    lines = group_words_into_lines(predictions)
    for line in lines:
        phrases = merge_words_in_line(line)
        for phrase in phrases:
            print("📝", phrase)

# ----------------- POSITIONAL MATCHING ------------------ #

INTITULES = {
    'numero_facture': ['facture', 'n° facture', 'no facture', 'facture no'],
    'date_facture': ['date facture', 'date de facture'],
    'client': ['client', 'n° client'],
    'total_ht': ['total ht', 'total net ht', 'brut h.t.', 'totali ht'],
    'tva': ['tva', 'total tva', 'total t.v.a.'],
    'net_a_payer': ['net à payer', 'total ttc', 'montant ttc'],
}

def match_fields_positionally(predictions):
    results = {}
    for field, keywords in INTITULES.items():
        for i, word in enumerate(predictions):
            val = word['value'].lower()
            for kw in keywords:
                if kw in val:
                    # Chercher à droite ou en dessous
                    ref_x, ref_y = word['bbox'][1][0], (word['bbox'][0][1] + word['bbox'][1][1]) / 2
                    for j, w2 in enumerate(predictions):
                        if i == j:
                            continue
                        w2_x, w2_y = w2['bbox'][0][0], (w2['bbox'][0][1] + w2['bbox'][1][1]) / 2
                        if abs(w2_y - ref_y) < 0.015 and w2_x > ref_x:
                            results[field] = w2['value']
                            break
                        if abs(w2_x - word['bbox'][0][0]) < 0.02 and w2_y > word['bbox'][1][1]:
                            results[field] = w2['value']
                            break
                    if field in results:
                        break
    return results

# ------------------------ MAIN ------------------------- #

if len(sys.argv) != 2:
    print("Usage: python3 kie_predictor.py <chemin_du_fichier>")
    sys.exit(1)

file_path = sys.argv[1]

# Détecte image ou PDF
if file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
    doc = DocumentFile.from_images(file_path)
else:
    doc = DocumentFile.from_pdf(file_path)

print(f"📥 Lecture du fichier : {file_path}")
print("📚 Chargement du modèle Doctr...")
model = kie_predictor(pretrained=True)

print("🔎 Prédiction OCR en cours...")
result = model(doc)

# Extraire toutes les prédictions
predictions = []
for page in result.pages:
    for block in page.blocks:
        for line in block.lines:
            for word in line.words:
                predictions.append({
                    'value': word.value,
                    'bbox': word.geometry,
                })

print("🧠 Reconstruction des phrases à partir des coordonnées :\n")
print_ocr_sentences(predictions)

print("\n🧠 🔎 Appariement positionnel des données clés :\n")
matched = match_fields_positionally(predictions)

for key, val in matched.items():
    print(f"🔗 {key} → {val}")
