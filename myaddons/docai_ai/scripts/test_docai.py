from google.cloud import documentai_v1 as documentai
import os

# Chemin de ta clé JSON
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/data/keys/docai-factures.json"

# Paramètres
project_id = "889157590963"
location = "eu"
processor_id = "a228740c1efe755d"
file_path = "/data/Documents/factures_archive/Facture_CCL_153880.pdf"

# Client
client = documentai.DocumentProcessorServiceClient()
name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

# Lire le fichier PDF
with open(file_path, "rb") as f:
    pdf_content = f.read()

raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")

# Envoyer la requête
request = documentai.ProcessRequest(name=name, raw_document=raw_document)
result = client.process_document(request=request)

# Afficher le texte brut détecté
document = result.document
print("=== Texte détecté ===")
print(document.text)
