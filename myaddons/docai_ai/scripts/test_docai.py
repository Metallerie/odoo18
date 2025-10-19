from google.cloud import documentai_v1 as documentai
import os

# Clé API
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/data/keys/docai-factures-1d0a66f84bff.json"

# Paramètres du processor
project_id = "889157590963"
location = "eu"  # Région correcte
processor_id = "a228740c1efe755d"
file_path = "/data/Documents/factures_archive/Facture_CCL_153880.pdf"

# ⚡ Forcer l’endpoint EU
client = documentai.DocumentProcessorServiceClient(
    client_options={"api_endpoint": f"{location}-documentai.googleapis.com"}
)

# Nom du processor
name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

# Charger le PDF
with open(file_path, "rb") as f:
    pdf_content = f.read()

raw_document = documentai.RawDocument(
    content=pdf_content,
    mime_type="application/pdf"
)

# Envoyer la requête
request = documentai.ProcessRequest(name=name, raw_document=raw_document)
result = client.process_document(request=request)

# Résultat
document = result.document

print("=== Texte détecté ===")
print(document.text[:1000])

print("\n=== Champs extraits ===")
for entity in document.entities:
    print(f"{entity.type_}: {entity.mention_text}")
