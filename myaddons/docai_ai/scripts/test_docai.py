
from google.cloud import documentai_v1 as documentai
import os

# chemin vers ta clé JSON
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/data/keys/docai-factures.json"

# paramètres
project_id = "docai-factures"   # ton Project ID
location = "eu"                 # ou "us", selon où ton processor est créé
processor_id = "889157590963"   # ID de ton processor (une suite de chiffres)

client = documentai.DocumentProcessorServiceClient()
name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

print("✅ Connexion réussie à Document AI :", name)
