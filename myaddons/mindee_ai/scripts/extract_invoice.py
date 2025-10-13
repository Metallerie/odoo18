# extract_invoice.py

import sys
import json
import tempfile
import subprocess
from pdf2image import convert_from_path

# --- OCR avec Tesseract ---
def run_tesseract(image_path, lang="fra"):
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

# --- Extraction des cases et OCR ---
def extract_cases(pdf_file, json_file):
    # Charger modèle
    with open(json_file, "r", encoding="utf-8") as f:
        model = json.load(f)

    # Charger le PDF en image
    pages = convert_from_path(pdf_file, dpi=300)
    page = pages[0]
    img_w, img_h = page.size

    print("=== Cases détectées avec OCR ===")
    for entry in model:
        # Chercher toutes les zones dans toutes les clés
        for key, zones in entry.items():
            if not isinstance(zones, list):
                continue
            for zone in zones:
                label_list = zone.get("rectanglelabels", [])
                label = label_list[0] if label_list else "NUL"

                # Position en pixels
                x, y, w, h = zone["x"], zone["y"], zone["width"], zone["height"]
                left = int((x / 100) * img_w)
                top = int((y / 100) * img_h)
                right = int(((x + w) / 100) * img_w)
                bottom = int(((y + h) / 100) * img_h)

                # OCR sur la zone
                crop = page.crop((left, top, right, bottom))
                with tempfile.NamedTemporaryFile(suffix=".PNG", delete=False) as tmp_img:
                    crop_path = tmp_img.name
                    crop.save(crop_path)

                text = run_tesseract(crop_path)

                # Afficher juste la case (sans section)
                print(f"[Case] {label} → x={x}, y={y}, w={w}, h={h} → {text}")

# --- Main ---
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_invoice.py <fichier.pdf> <modele.json>")
        sys.exit(1)

    extract_cases(sys.argv[1], sys.argv[2])
