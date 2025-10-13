# extract_invoice.py
import sys
import json
import logging
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

def load_model(model_file):
    with open(model_file, "r", encoding="utf-8") as f:
        return json.load(f)

def extract_invoice(pdf_file, model):
    logging.info(f"Conversion du PDF en images : {pdf_file}")
    pages = convert_from_path(pdf_file)
    results = {}

    # On prend uniquement la première page (si factures sur 1 page)
    page = pages[0]

    for ann in model:
        ann_id = ann.get("id", None)
        annotations = ann.get("annotations", [])

        for a in annotations:
            for r in a.get("result", []):
                field_name = r["value"]["labels"][0]
                rect = r["value"].get("rectanglelabels", None)

                # Coordonnées relatives (x, y, width, height)
                x = r["value"].get("x", 0)
                y = r["value"].get("y", 0)
                w = r["value"].get("width", 0)
                h = r["value"].get("height", 0)

                # Convertir en pixels absolus
                img_w, img_h = page.size
                left = int(x * img_w / 100)
                top = int(y * img_h / 100)
                right = int((x + w) * img_w / 100)
                bottom = int((y + h) * img_h / 100)

                cropped = page.crop((left, top, right, bottom))

                # OCR sur la zone
                text = pytesseract.image_to_string(cropped, lang="fra").strip()
                results[field_name] = text if text else ""

                logging.debug(f"[{field_name}] Zone=({left},{top},{right},{bottom}) → '{results[field_name]}'")

    return results

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_invoice.py <fichier.pdf> <modele.json>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    model_file = sys.argv[2]

    model = load_model(model_file)
    extracted = extract_invoice(pdf_file, model)

    print("\n=== Résultats OCR par champ ===")
    for k, v in extracted.items():
        print(f"{k:15} : {v}")
