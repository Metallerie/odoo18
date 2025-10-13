def extract_invoice(pdf_path, model):
    results = []

    # Texte du PDF
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    logging.debug(f"Texte extrait du PDF ({len(full_text)} caractères)")

    # 🔎 Récupération des annotations Label Studio
    annotations = []
    if isinstance(model, list) and model:
        anns = model[0].get("annotations", [])
        if anns and "result" in anns[0]:
            annotations = anns[0]["result"]

    logging.info(f"{len(annotations)} annotations trouvées dans le modèle")

    # On boucle sur les champs
    for ann in annotations:
        value = ann.get("value", {})
        label = value.get("labels", ["inconnu"])[0]

        # Pas de texte dans le JSON → on va le chercher dans le PDF
        found = None
        if label == "invoice_number":
            match = re.search(r"FACTURE\s*[:N°]*\s*(\d+)", full_text, re.IGNORECASE)
            if match:
                found = match.group(1)

        elif label == "invoice_date":
            match = re.search(r"Date\s*facture\s*[:]*\s*(\d{2}/\d{2}/\d{4})", full_text, re.IGNORECASE)
            if match:
                found = match.group(1)

        results.append((label, found or "❌ non trouvé"))

    return results
