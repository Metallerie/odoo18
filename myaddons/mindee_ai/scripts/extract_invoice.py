# -*- coding: utf-8 -*-
# /data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/scripts/extract_invoice.py

import sys
import json
import logging
import tempfile
import subprocess
from pdf2image import convert_from_path

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


# ---------- OCR avec Tesseract ----------
def run_tesseract(image_path, lang="fra"):
    """Exécute Tesseract OCR et retourne le texte reconnu ou 'NUL' si vide."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        output_path = tmp.name.replace(".txt", "")
    cmd = ["tesseract", image_path, output_path, "-l", lang, "txt"]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    try:
        with open(output_path + ".txt", "r", encoding="utf-8") as f:
            text = f.read().strip()
        return text if text else "NUL"
    except FileNotFoundError:
        return "NUL"


# ---------- Extraction ----------
def extract_from_pdf(pdf_path, json_path):
    logging.info(f"Chargement du modèle JSON : {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        model = json.load(f)

    logging.info(f"Conversion du PDF en images : {pdf_path}")
    pages = convert_from_path(pdf_path, dpi=300)

    structured = {"Header": {}, "Table": {}, "Footer": {}, "Document": {}}

    for entry in model:
        doc_id = entry.get("id", "N/A")
        zones = entry.get("Document", [])
        logging.debug(f"Analyse entrée JSON id={doc_id} avec {len(zones)} zones")

        row_index = 1
        for idx, zone in enumerate(zones, start=1):
            label_list = zone.get("rectanglelabels", [])
            label = label_list[0] if label_list else f"Zone_{idx}"

            # coords relatives → absolues
            x, y, w, h = zone["x"], zone["y"], zone["width"], zone["height"]
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

            # Organisation hiérarchique par type de bloc
            if "Header" in label:
                structured["Header"][label] = ocr_text
            elif "Table" in label:
                structured["Table"].setdefault(f"Row[{row_index}]", {})[label] = ocr_text
                row_index += 1
            elif "Footer" in label:
                structured["Footer"][label] = ocr_text
            else:
                structured["Document"][label] = ocr_text

    return structured


# ---------- Normalisation ----------
def normalize_values(data):
    """
    Remplace toutes les valeurs vides ou None par 'NUL' récursivement.
    """
    if isinstance(data, dict):
        return {k: normalize_values(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [normalize_values(v) for v in data]
    else:
        if data is None or (isinstance(data, str) and data.strip() == ""):
            return "NUL"
        return data


# ---------- Affichage hiérarchique ----------
def print_tree(data, indent=0):
    """Affiche la structure JSON en arbre indenté."""
    for key, value in data.items():
        if isinstance(value, dict):
            print(" " * indent + f"{key}")
            print_tree(value, indent + 4)
        else:
            print(" " * indent + f"{key} : {value}")


# ---------- Main ----------
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_invoice.py <fichier.pdf> <modele.json>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    json_file = sys.argv[2]

    structured = extract_from_pdf(pdf_file, json_file)

    # 🔥 Remplacement des champs vides
    structured = normalize_values(structured)

    print("\n=== Résultats OCR hiérarchiques (indentés) ===")
    print_tree(structured, indent=0)
