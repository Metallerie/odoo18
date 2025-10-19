from google.cloud import documentai_v1 as documentai

project_id = "889157590963"
location = "us"
processor_id = "a228740c1efe755d"
key_path = "/data/keys/docai-factures-1d0a66f84bff.json"

client = documentai.DocumentProcessorServiceClient.from_service_account_json(key_path)

# Chemin complet du processor
name = eu-documentai.googleapis.com/v1/projects/889157590963/locations/eu/processors/a228740c1efe755d
# name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"
print(name)
with open("/data/Documents/factures_archive/Facture_CCL_153880.pdf", "rb") as f:
    raw_document = documentai.RawDocument(content=f.read(), mime_type="application/pdf")

request = documentai.ProcessRequest(name=name, raw_document=raw_document)
result = client.process_document(request=request)

print("✅ Document traité avec succès")
print("Texte extrait :", result.document.text[:500])
