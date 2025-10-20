def action_test_docai_connection(self):
    import os
    from google.cloud import documentai_v1 as documentai

    project_id = self.docai_project_id
    location = self.docai_location
    processor_id = self.docai_invoice_processor_id
    key_path = self.docai_key_path
    test_invoice = self.docai_test_invoice_path

    if not (project_id and location and processor_id and key_path and test_invoice):
        raise UserError("⚠️ Paramètres Document AI incomplets.")

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
    client = documentai.DocumentProcessorServiceClient(
        client_options={"api_endpoint": f"{location}-documentai.googleapis.com"}
    )
    name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

    _logger.info("👉 Test connexion DocAI")
    _logger.info("   project_id: %s", project_id)
    _logger.info("   location: %s", location)
    _logger.info("   processor_id: %s", processor_id)
    _logger.info("   endpoint: %s-documentai.googleapis.com", location)
    _logger.info("   name utilisé: %s", name)

    with open(test_invoice, "rb") as f:
        pdf_content = f.read()

    raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)

    try:
        result = client.process_document(request=request)
        doc = result.document
        _logger.info("✅ Connexion réussie. Entities: %s",
                     [f"{e.type_}:{e.mention_text}" for e in doc.entities[:5]])
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Succès",
                "message": "Connexion OK ✅. %d entités détectées." % len(doc.entities),
                "sticky": False,
            },
        }
    except Exception as e:
        _logger.error("❌ Erreur connexion Document AI : %s", e, exc_info=True)
        raise UserError("❌ Erreur connexion Document AI : %s" % e)
