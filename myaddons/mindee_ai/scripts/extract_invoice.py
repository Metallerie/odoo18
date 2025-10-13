# -*- coding: utf-8 -*-
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import json
import logging
import sys

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s - %(message)s")

def load_model(model_file):
    logging.info(f"Chargement du modèle JSON : {model_file}")
    with open(model_file, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            logging.debug(f"JSON chargé : type={type(data)} taille={len(data)}")
            return data
        except Exception as e:
            logging.error(f"Erreur de parsing JSON : {e}")
            return []

def extract_invoice(pdf_path, model):
    logging.info(f"Ouverture du PDF : {pdf_path}")
    doc = fitz.open(pdf_path)
    results = {}

    for entry in model:
        logging.debug(f"Analyse d'une entrée JSON : {entry.get('id', 'sans id')}")
        annotations = entry.get("annotations", [])
        logging.debug(f"  Nombre d'annotations trouvées : {len(annotations)}")

        for ann in annotations:
            for res in ann.get("result", []):
                value = res.get("value", {})
                labels = value.get("labels", ["inconnu"])
                bbox = value.get("rectanglelabels", None)

                # Log des valeurs JSON
                logging.debug(f"    Champ {labels} - value keys: {list(value.keys())}")

                # Vérifie présence coordonnées
                x = value.get("x")
                y = value.get("y")
                w = value.get("width")
                h = value.get("height")
                page = value.get("page", 1)

                logging.debug(f"    Coordonnées : x={x}, y={y}, w={w}, h={h}, page={page}")

                if None in (x, y, w, h):
                    logging.warning(f"    ⚠️ Pas de bbox pour {labels}, on saute")
                    results[labels[0]] = ""
                    continue

                # Conversion des coordonnées (Label Studio donne en %)
                page_index = page - 1
                page_rect = doc[page_index].rect
                rect = fitz.Rect(
                    page_rect.x0 + (x/100.0)*page_rect.width,
                    page_rect.y0 + (y/100.0)*page_rect.height,
                    page_rect.x0 + ((x+w)/100.0)*page_rect.width,
                    page_rect.y0 + ((y+h)/100.0)*page_rect.height
                )

                logging.debug(f"    Zone réelle PDF : {rect}")

                # Découpe image
                pix = doc[page_index].get_pixmap(clip=rect)
                img = Image.open(io.BytesIO(pix.tobytes("png")))

                text = pytesseract.image_to_string(img, lang="fra")
                logging.info(f"    OCR pour {labels} : {text.strip()}")
                results[labels[0]] = text.strip()

    return results

def main(pdf_file, model_file):
    model = load_model(model_file)
    if not model:
        logging.error("Modèle JSON vide ou incorrect")
        return

    extracted = extract_invoice(pdf_file, model)

    print("\n=== Résultats OCR par champ ===")
    for champ, valeur in extracted.items():
        print(f"{champ:20s} -> {valeur}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python extract_invoice.py <facture.pdf> <modele.json>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
