from google.cloud import documentai_v1 as documentai
import os

# Chemin vers ta clé JSON
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/data/keys/docai-factures-1d0a66f84bff.json"

# Paramètres du processor
project_id = "889157590963"
location = "eu"  # bien Europe
processor_id = "a228740c1efe755d"
file_path = "/data/Documents/factures_archive/Facture_CCL_153880.pdf"

# Client
client = documentai.DocumentProcessorServiceClient()
name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

# Charger ton PDF
with open(file_path, "rb") as f:
    pdf_content = f.read()

raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")

# Envoyer la requête
request = documentai.ProcessRequest(name=name, raw_document=raw_document)
result = client.process_document(request=request)

# Récupérer le document
document = result.document

print("=== Texte détecté ===")
print(document.text[:1000])  # affiche seulement les 1000 premiers caractères

print("\n=== Champs extraits ===")
for entity in document.entities:
    print(f"{entity.type_}: {entity.mention_text}")
