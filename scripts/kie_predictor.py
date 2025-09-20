#doc = DocumentFile.from_pdf("/data/Documents/factures_archive/3259598_trenois.pdf_imported")

from doctr.io import DocumentFile
from doctr.models import kie_predictor

# Model
model = kie_predictor(det_arch='db_resnet50', reco_arch='crnn_vgg16_bn', pretrained=True)
# PDF
doc = DocumentFile.from_pdf("/data/Documents/factures_archive/3259598_trenois.pdf_imported")
# Analyze
result = model(doc)

predictions = result.pages[0].predictions
for class_name in predictions.keys():
    list_predictions = predictions[class_name]
    for prediction in list_predictions:
        print(f"Prediction for {class_name}: {prediction}")
