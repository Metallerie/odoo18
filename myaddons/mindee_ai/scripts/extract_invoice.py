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


# ---------- Temps 1 : Définir les cases ----------
def load_model(json_file):
    """Charge le modèle JSON (définition des zones/labels)."""
    with open(json_file, "r", encoding="utf-8") as f:
        return json.load(f)


def define_cases(model, img_size):
    """Transforme les coordonnées relatives du JSON en coordonnées pixels."""
    cases = []
    img_w, img_h = img_size

    for entry in model:
        zones = entry.get("Document", [])
        for idx, zone in enumerate(zones, start=1):
            label_list = zone.get("rectanglelabels", [])
            label = label_list[0] if label_list else f"Zone_{idx}"

            # Coordonnées relatives → absolues
            x, y, w, h = zone["x"], zone["y"], zone["width"], zone["height"]
            left = int((x / 100) * img_w)
            top = int((y / 100) * img_h)
            right = int(((x + w) / 100) * img_w)
            bottom = int(((y + h) / 100) * img_h)

            cases.append({
                "label": label,
                "coords": (left, top, right, bottom)
            })

    return cases


# ---------- Temps 2 : Lire les cases ----------
def read_case(page, case, margin=0.02):
    """Extrait une case, applique OCR, renvoie le texte ou 'NUL'."""
    left, top, right, bottom = case["coords"]

    # Ajuster la box pour éviter débordement
    w = right - left
    h = bottom - top
    left += int(w * margin)
    top += int(h * margin)
    right -= int(w * margin)
    bottom -= int(h * margin)

    crop = page.crop((left, top, right, bottom))
    with tempfile.NamedTemporaryFile(suffix=".PNG", delete=False) as tmp_img:
        crop_path = tmp_img.name
        crop.save(crop_path)

    return run_tesseract(crop_path)


def fill_structure(cases, pages):
    """Construit la structure hiérarchique (Header/Table/Footer/Document)."""
    structured = {"Header": {}, "Table": {}, "Footer": {}, "Document": {}}
    row_index = 1

    for case in cases:
        label = case["label"]
        ocr_text = read_case(pages[0], case)  # on suppose 1 page pour l’instant

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
def main(pdf_file, json_file):
    logging.info(f"Chargement du modèle JSON : {json_file}")
    model = load_model(json_file)

    logging.info(f"Conversion du PDF en images : {pdf_file}")
    pages = convert_from_path(pdf_file, dpi=300)

    # Temps 1 : définir les cases
    cases = define_cases(model, pages[0].size)

    # Temps 2 : lire les cases
    structured = fill_structure(cases, pages)

    print("\n=== Résultats OCR hiérarchiques (indentés) ===")
    print_tree(structured, indent=0)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_invoice.py <fichier.pdf> <modele.json>")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
