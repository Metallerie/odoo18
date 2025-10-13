# -*- coding: utf-8 -*-
import sys
import json
import logging
import tempfile
import subprocess
from pathlib import Path
from pdf2image import convert_from_path
from tabulate import tabulate

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

def load_model(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        model = json.load(f)
    logging.debug("JSON chargé : type=%s taille=%d", type(model), len(model))
    return model

def run_ocr_on_zone(image, zone, label):
    """Extrait une zone et applique Tesseract OCR"""
    x = zone["x"] / 100 * zone["original_width"]
    y = zone["y"] / 100 * zone["original_height"]
    w = zone["width"] / 100 * zone["original_width"]
    h = zone["height"] / 100 * zone["original_height"]

    crop = image.crop((x, y, x + w, y + h))

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        crop.save(tmp.name)
        output_txt = tmp.name.replace(".png", "")
        cmd = ["tesseract", tmp.name, output_txt, "-l", "fra", "txt"]
        logging.debug("CMD OCR %s", cmd)
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        try:
            with open(output_txt + ".txt", "r", encoding="utf-8") as f:
                text = f.read().strip()
        except FileNotFoundError:
            text = ""

    return label, text if text else "NUL"

def extract_invoice(pdf_path, model):
    logging.info("Conversion du PDF en images : %s", pdf_path)
    images = convert_from_path(pdf_path)

    results = {}

    for entry in model:
        entry_id = entry.get("id")
        zones = entry.get("Document", [])
        logging.debug("Analyse entrée JSON id=%s avec %d zones", entry_id, len(zones))

        for zone in zones:
            labels = zone.get("rectanglelabels", [])
            if not labels:
                continue
            label = labels[0]
            page = images[0]  # ⚠️ simplification : 1 page
            _, text = run_ocr_on_zone(page, zone, label)
            results[label] = text if text else "NUL"

    return results

def main(pdf_file, model_file):
    model = load_model(model_file)
    results = extract_invoice(pdf_file, model)

    print("\n=== Résultats OCR par champ ===")
    table_data = []
    for champ, valeur in results.items():
        table_data.append([champ, valeur])
    print(tabulate(table_data, headers=["Champ", "Valeur OCR"], tablefmt="grid"))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python extract_invoice.py <fichier.pdf> <modele.json>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    model_file = sys.argv[2]
    main(pdf_file, model_file)
