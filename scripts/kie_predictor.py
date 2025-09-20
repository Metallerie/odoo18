import json
from doctr.io import DocumentFile
from doctr.models import kie_predictor

# Modèle OCR
model = kie_predictor(det_arch='db_resnet50', reco_arch='crnn_vgg16_bn', pretrained=True)

# Charger un PDF
doc = DocumentFile.from_pdf("/data/Documents/factures_archive/3259598_trenois.pdf_imported")

# OCR
result = model(doc)

predictions = result.pages[0].predictions

# Regrouper en phrases simples
def group_predictions(preds):
    grouped = []
    current = ""
    for pred in preds:
        word = pred.value.strip()
        if not word:
            continue
        if current == "":
            current = word
        else:
            # Ici règle simplifiée : toujours concaténer avec espace
            current += " " + word
        # Option : si le mot finit par un signe de ponctuation ou un numéro → on ferme la phrase
        if word.endswith(".") or word.isdigit():
            grouped.append(current.strip())
            current = ""
    if current:
        grouped.append(current.strip())
    return grouped

# Construire les blocs JSON
json_blocks = {}
for class_name, list_predictions in predictions.items():
    grouped_phrases = group_predictions(list_predictions)
    json_blocks[class_name] = [{"text": phrase} for phrase in grouped_phrases]

# Afficher JSON formaté
print(json.dumps(json_blocks, indent=2, ensure_ascii=False))
