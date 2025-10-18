# -*- coding: utf-8 -*-
#scripts indépendant conection docai
import os
import json
import logging
from google.cloud import documentai_v1 as documentai

_logger = logging.getLogger(__name__)

class DocAIClient:
    def __init__(self, project_id, processor_id, location, key_path):
        self.project_id = project_id
        self.processor_id = processor_id
        self.location = location
        self.key_path = key_path

        if key_path and os.path.exists(key_path):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
        else:
            _logger.warning("⚠️ Chemin de clé Google introuvable : %s", key_path)

        self.client = documentai.DocumentProcessorServiceClient()
        self.name = f"projects/{self.project_id}/locations/{self.location}/processors/{self.processor_id}"

    def process_invoice(self, file_content, mime_type="application/pdf"):
        """Envoie un PDF/Image à DocAI et retourne le JSON"""
        document = {"content": file_content, "mime_type": mime_type}
        result = self.client.process_document(request={"name": self.name, "raw_document": document})
        return documentai.Document.to_dict(result.document)
