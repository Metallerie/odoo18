
import json
from doctr.models import ocr_predictor
from doctr.io import DocumentFile

# Charger modèle OCR
model = ocr_predictor(pretrained=True)

# Charger ton PDF (remplace par ton chemin facture)
doc = DocumentFile.from_pdf("/data/Documents/factures_archive/Facture_CCL_161372.pdf")

# OCR
result = model(doc)

# Exporter et afficher en JSON lisible
print(json.dumps(result.export(), indent=2, ensure_ascii=False))
