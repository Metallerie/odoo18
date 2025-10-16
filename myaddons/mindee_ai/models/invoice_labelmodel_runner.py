# -*- coding: utf-8 -*-
import json
import tempfile
import subprocess
import logging
from pdf2image import convert_from_path

_logger = logging.getLogger(__name__)

# --- OCR avec Tesseract ---
def run_tesseract(image_path, lang="fra"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        output_path = tmp.name.replace(".txt", "")
    cmd = ["tesseract", image_path, output_path, "-l", lang, "txt"]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    try:
        with open(output_path + ".txt", "r", encoding="utf-8") as f:
            text = f.read().strip()
        return text if text else ""
    except FileNotFoundError:
        return ""


# --- Extraction des zones selon modèle ---
def extract_cases(pdf_file, json_file):
    """
    Retourne un dict avec l'OCR par zones selon le modèle JSON.
    Sert pour Odoo ET pour l'entraînement IA.
    """
    results = {
        "file_name": pdf_file,
        "pages": []
    }

    # Charger modèle
    with open(json_file, "r", encoding="utf-8") as f:
        model = json.load(f)

    # Charger le PDF en image (première page uniquement pour l'instant)
    pages = convert_from_path(pdf_file, dpi=300)
    page = pages[0]
    img_w, img_h = page.size

    page_result = {"page": 1, "zones": []}
    _logger.warning("📄 [OCR] PDF=%s W=%s H=%s", pdf_file, img_w, img_h)

    for entry in model:
        for key, zones in entry.items():
            if not isinstance(zones, list):
                continue
            for zone in zones:
                if not isinstance(zone, dict):
                    continue

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

                zone_result = {
                    "label": label,
                    "x": x, "y": y, "w": w, "h": h,
                    "text": text
                }
                page_result["zones"].append(zone_result)

                _logger.warning("🔎 [OCR][%s] → %s", label, text)

    results["pages"].append(page_result)
    return results


# --- OCR brut façon console ---
def pretty_print_results(results):
    """
    Retourne une version texte brute style console pour debug/stockage dans Odoo.
    """
    lines = ["=== Cases détectées avec OCR (dynamique) ==="]
    for page in results.get("pages", []):
        for zone in page.get("zones", []):
            label = zone.get("label", "NUL")
            x, y, w, h = zone["x"], zone["y"], zone["w"], zone["h"]
            text = zone.get("text", "")
            lines.append(f"[{label}] x={x}, y={y}, w={w}, h={h} → {text}")
    return "\n".join(lines)


# --- Debug CLI (optionnel) ---
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python partner_invoice_labelmodel.py <fichier.pdf> <modele.json>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    json_file = sys.argv[2]

    data = extract_cases(pdf_file, json_file)
    print(pretty_print_results(data))
    print(json.dumps(data, indent=2, ensure_ascii=False))
