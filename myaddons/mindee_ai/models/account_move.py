from doctr.models import kie_predictor
from doctr.io import DocumentFile
import sys
import json

if len(sys.argv) != 2:
    print("Usage: python3 kie_predictor_runner.py <chemin_du_fichier_PDF>")
    sys.exit(1)

pdf_path = sys.argv[1]

# Charger le PDF
doc = DocumentFile.from_pdf(pdf_path)

# Charger le modèle KIE
model = kie_predictor(pretrained=True)
result = model(doc)

# Exporter en JSON (format Doctr standard)
exported = result.export()

# Retourner proprement
print(json.dumps(exported, ensure_ascii=False, indent=2))
