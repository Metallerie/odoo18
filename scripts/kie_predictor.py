from doctr.models import ocr_predictor
from doctr.io import DocumentFile
import sys
import json  # Ajout pour le format JSON

# ----------- 🔧 Fonctions OCR reconstruction ----------------

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

def get_ocr_sentences(predictions, y_thresh=0.01, x_gap_thresh=0.02):
    """Retourne les phrases reconstituées à partir des prédictions OCR."""
    sentences = []
    lines = group_words_into_lines(predictions, y_thresh=y_thresh)
    for line in lines:
        phrases = merge_words_in_line(line, x_gap_thresh=x_gap_thresh)
        sentences.extend(phrases)
    return sentences

# ----------- 📄 Chargement du fichier ----------------

if len(sys.argv) != 2:
    print("Usage: python3 kie_predictor.py <chemin_du_fichier_PDF>")
    sys.exit(1)

pdf_path = sys.argv[1]

# ----------- 🔍 Lancement OCR doctr -------------------

print("📥 Lecture du fichier :", pdf_path)
doc = DocumentFile.from_pdf(pdf_path)

print("📚 Chargement du modèle Doctr...")
model = ocr_predictor(pretrained=True)

print("🔎 Prédiction OCR en cours...")
result = model(doc)

# ----------- 📦 Extraction et regroupement -------------

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
sentences = get_ocr_sentences(predictions)

# Affichage en JSON
print(json.dumps({"phrases": sentences}, ensure_ascii=False, indent=2))
