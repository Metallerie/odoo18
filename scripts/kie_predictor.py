#doc = DocumentFile.from_pdf("/data/Documents/factures_archive/3259598_trenois.pdf_imported")

# scripts/kie_predictor.py

from doctr.models import ocr_predictor
from doctr.io import DocumentFile
import sys

# ----------- 🔧 Fonctions OCR reconstruction ----------------

def group_words_into_lines(predictions, y_thresh=0.01):
    """Regroupe les mots sur des lignes selon leur coordonnée Y moyenne."""
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
    """Fusionne les mots proches horizontalement en phrases."""
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

def print_ocr_sentences(predictions, y_thresh=0.01, x_gap_thresh=0.02):
    """Affiche les phrases reconstituées à partir des prédictions OCR."""
    lines = group_words_into_lines(predictions, y_thresh=y_thresh)
    for line in lines:
        phrases = merge_words_in_line(line, x_gap_thresh=x_gap_thresh)
        for phrase in phrases:
            print("📝", phrase)

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
    for word in page.predictions:
        predictions.append({
            'value': word.value,
            'bbox': word.bbox,
        })

print("🧠 Reconstruction des phrases à partir des coordonnées :\n")
print_ocr_sentences(predictions)
