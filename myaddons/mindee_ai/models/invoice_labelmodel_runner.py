# extract_invoice.py (version avec JSON)
# Usage:
#   python extract_invoice.py <fichier.pdf> <modele.json> [--json-out /chemin/sortie.json]

import sys
import json
import tempfile
import subprocess
from pathlib import Path
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

def _get_coords(zone):
    """Récupère x,y,w,h depuis la racine ou zone['value'] (tolérant selon export LS)."""
    v = zone.get("value") or {}
    x = zone.get("x", v.get("x"))
    y = zone.get("y", v.get("y"))
    w = zone.get("width", v.get("width"))
    h = zone.get("height", v.get("height"))
    if x is None or y is None or w is None or h is None:
        return None
    return float(x), float(y), float(w), float(h)

# --- Extraction des cases et OCR ---
def extract_cases(pdf_file, json_file, json_out_path=None):
    # Charger modèle
    with open(json_file, "r", encoding="utf-8") as f:
        model = json.load(f)

    # Charger le PDF en image
    pages = convert_from_path(pdf_file, dpi=300)
    page = pages[0]
    img_w, img_h = page.size

    # OCR brut page entière
    page_text = run_tesseract(_save_temp_img(page))

    print("=== Cases détectées avec OCR (dynamique) ===")
    all_cases = []

    for entry in model:
        for key, zones in entry.items():
            if not isinstance(zones, list):
                continue  # skip si ce n’est pas une liste
            for zone in zones:
                if not isinstance(zone, dict):
                    continue  # skip si pas un dict

                label_list = zone.get("rectanglelabels", [])
                label = label_list[0] if label_list else "NUL"

                coords = _get_coords(zone)
                if coords is None:
                    continue
                x, y, w, h = coords

                # Position en pixels
                left = int((x / 100) * img_w)
                top = int((y / 100) * img_h)
                right = int(((x + w) / 100) * img_w)
                bottom = int(((y + h) / 100) * img_h)

                # OCR sur la zone
                crop_path = _save_temp_crop(page, left, top, right, bottom)
                text = run_tesseract(crop_path)

                # Afficher résultat "tel quel"
                print(f"[{label}] x={x}, y={y}, w={w}, h={h} → {text}")

                # Accumuler pour JSON
                all_cases.append({
                    "label": label,
                    "x": x, "y": y, "w": w, "h": h,
                    "text": text
                })

    # Construire le JSON final
    filled_cases = [c for c in all_cases if (c.get("text") or "").strip() and c["text"].strip().upper() != "NUL"]

    result = {
        "ocr_raw": page_text,
        "ocr_zones_all": all_cases,        # toutes les cases (comme l’affichage)
        "ocr_zones_filled": filled_cases,  # uniquement cases remplies (≠ NUL)
    }

    # Sortie JSON facultative vers fichier
    if json_out_path:
        outp = Path(json_out_path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        with open(outp, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n>>> JSON écrit dans: {outp}")

    # Et on affiche aussi le JSON sur stdout à la fin si pas de fichier fourni
    if not json_out_path:
        print("\n=== JSON (aperçu) ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))

def _save_temp_img(pil_img):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        pil_img.save(tmp.name)
        return tmp.name

def _save_temp_crop(page_img, left, top, right, bottom):
    crop = page_img.crop((left, top, right, bottom))
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
        crop.save(tmp_img.name)
        return tmp_img.name

# --- Main ---
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python extract_invoice.py <fichier.pdf> <modele.json> [--json-out /chemin/sortie.json]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    model_path = sys.argv[2]
    json_out = None
    if len(sys.argv) >= 5 and sys.argv[3] == "--json-out":
        json_out = sys.argv[4]

    extract_cases(pdf_path, model_path, json_out_path=json_out)
