from doctr.io import DocumentFile
from doctr.models import kie_predictor

# Charger modèle
model = kie_predictor(det_arch='db_resnet50', reco_arch='crnn_vgg16_bn', pretrained=True)

# Charger le PDF
doc = DocumentFile.from_pdf("/data/Documents/factures_archive/3259598_trenois.pdf_imported")

# Analyser
result = model(doc)

# On prend la première page
predictions = result.pages[0].predictions

# Fonction de regroupement par espace
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
            # Si le mot commence par une majuscule ou si le précédent finit par un espace → même phrase
            if not word.startswith(" "):
                current += " " + word
            else:
                grouped.append(current)
                current = word
    if current:
        grouped.append(current)
    return grouped

# Boucle sur les classes
for class_name, list_predictions in predictions.items():
    grouped_phrases = group_predictions(list_predictions)
    print(f"===== {class_name} =====")
    for phrase in grouped_phrases:
        print("→", phrase)
