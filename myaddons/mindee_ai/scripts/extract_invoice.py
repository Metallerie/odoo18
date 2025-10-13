# -*- coding: utf-8 -*-
import sys
import json
import logging
import tempfile
import subprocess
from pdf2image import convert_from_path
from tabulate import tabulate

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

def run_tesseract(image_path, lang="fra"):
    """Exécute tesseract OCR et retourne le texte reconnu."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        output_path = tmp.name.replace(".txt", "")
    cmd = ["tesseract", image_path, output_path, "-l", lang, "txt"]
    logging.debug(f"Commande OCR : {' '.join(cmd)}")
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    try:
        with open(output_path + ".txt", "r", encoding="utf-8") as f:
            text = f.read().strip()
        return text if text else "NUL"
    except FileNotFoundError:
        return "NUL"

def extract_from_pdf(pdf_path, json_path):
    # Charger le JSON (zones annotées)
    logging.info(f"Chargement du modèle JSON : {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        model = json.load(f)

    # Convertir le PDF en images
    logging.info(f"Conversion du PDF en images : {pdf_path}")
    pages = convert_from_path(pdf_path, dpi=300)

    results = []
    for entry in model:
        doc_id = entry.get("id", "N/A")
        zones = entry.get("Document", [])
        logging.debug(f"Analyse entrée JSON id={doc_id} avec {len(zones)} zones")

        for idx, zone in enumerate(zones, start=1):
            label_list = zone.get("rectanglelabels", [])
            label = label_list[0] if label_list else f"Zone_{idx}"
            x, y, w, h = zone["x"], zone["y"], zone["width"], zone["height"]

            # Coords relatives → absolues
            page = pages[0]
            img_w, img_h = page.size
            left = int((x / 100) * img_w)
            top = int((y / 100) * img_h)
            right = int(((x + w) / 100) * img_w)
            bottom = int(((y + h) / 100) * img_h)

            crop = page.crop((left, top, right, bottom))
            with tempfile.NamedTemporaryFile(suffix=".PNG", delete=False) as tmp_img:
                crop_path = tmp_img.name
                crop.save(crop_path)

            ocr_text = run_tesseract(crop_path)

            # Construction clé hiérarchique
            parent = "Document"
            if "Header" in label:
                parent = "Header"
            elif "Table" in label:
                parent = "Table.Row[1]"  # simplifié pour test
            elif "Footer" in label:
                parent = "Footer"

            key = f"{parent}.{label}"
            results.append((key, ocr_text))

    return results

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_invoice.py <fichier.pdf> <modele.json>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    json_file = sys.argv[2]

    data = extract_from_pdf(pdf_file, json_file)

    print("\n=== Résultats OCR hiérarchiques ===")
    print(tabulate(data, headers=["Champ", "Valeur OCR"], tablefmt="grid"))
