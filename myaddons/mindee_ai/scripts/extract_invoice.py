#!/usr/bin/env python3
# extract_invoice.py
# Usage:
#   python3 extract_invoice.py <input_pdf_or_image> <model_json> [<output_json>]
#
# Dépendances:
#   pip install pillow tabulate pdf2image
#   poppler (system) pour pdf2image (si input est un PDF)
#   tesseract (system) + dictionnaire 'fra' si tu veux de meilleurs résultats

import sys
import os
import json
import subprocess
import logging
import tempfile
from pathlib import Path
from tabulate import tabulate

from PIL import Image

# Optional import; used only if input is PDF
try:
    from pdf2image import convert_from_path
except Exception:
    convert_from_path = None

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s - %(message)s")


def safe_value(val):
    """Convertit la valeur OCR pour affichage/JSON final."""
    if val is None:
        return "NUL"
    if isinstance(val, str):
        if val.strip() == "":
            return "VIDE"
        return val
    # listes, dicts, numbers -> stringifiy
    if isinstance(val, list):
        if not val:
            return "VIDE"
        return "\n".join([safe_value(v) for v in val])
    return str(val)


def run_tesseract(png_path, lang="fra"):
    """Appelle tesseract en ligne de commande et renvoie le texte brut."""
    # crée un fichier temporaire pour la sortie tesseract (base path sans extension)
    base_out = png_path + "_tess_out"
    cmd = ["tesseract", png_path, base_out, "-l", lang, "txt"]
    logging.debug("DEBUG - " + " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        txt_path = base_out + ".txt"
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read().strip()
            # nettoie le fichier txt pour éviter accumulation
            try:
                os.remove(txt_path)
            except Exception:
                pass
            return text
        return ""
    except subprocess.CalledProcessError as e:
        logging.error("Tesseract failed: %s", e)
        return ""
    except FileNotFoundError:
        logging.error("Tesseract not found. Install tesseract on your system.")
        return ""


def ensure_images_from_input(input_path, tmpdir, dpi=300):
    """Si input_path est un PDF => convertit en images (1 par page). 
       Sinon si c'est une image, la renvoie telle quelle."""
    input_path = Path(input_path)
    images = []
    if input_path.suffix.lower() in [".pdf"]:
        if convert_from_path is None:
            logging.error("pdf2image.convert_from_path absent. Installe pdf2image et poppler.")
            return images
        logging.info("Conversion du PDF en images : %s", str(input_path))
        pil_images = convert_from_path(str(input_path), dpi=dpi)
        for i, img in enumerate(pil_images, start=1):
            out = Path(tmpdir) / f"page_{i}.png"
            img.save(out, format="PNG")
            images.append(str(out))
    else:
        # on suppose image unique (png/jpg)
        images.append(str(input_path))
    return images


def crop_region_save(image_path, zone, tmpdir):
    """
    Recadre une zone (les coords sont en % par rapport à original_width/original_height)
    zone: dict avec x, y, width, height, original_width, original_height
    retourne le chemin du png créé.
    """
    img = Image.open(image_path)
    img_w, img_h = img.size

    # If original dimensions present and seem different, compute using percentage.
    # Dans ton JSON, x,y,width,height semblent être en pourcentage (0..100)
    x_pct = float(zone.get("x", 0))
    y_pct = float(zone.get("y", 0))
    w_pct = float(zone.get("width", 100))
    h_pct = float(zone.get("height", 100))

    # map percentages -> pixels
    left = int(round((x_pct / 100.0) * img_w))
    top = int(round((y_pct / 100.0) * img_h))
    right = int(round(((x_pct + w_pct) / 100.0) * img_w))
    bottom = int(round(((y_pct + h_pct) / 100.0) * img_h))

    # clamp
    left = max(0, min(left, img_w - 1))
    top = max(0, min(top, img_h - 1))
    right = max(left + 1, min(right, img_w))
    bottom = max(top + 1, min(bottom, img_h))

    cropped = img.crop((left, top, right, bottom))
    out_path = Path(tmpdir) / f"crop_{left}_{top}_{right}_{bottom}.png"
    cropped.save(out_path, format="PNG")
    return str(out_path)


def process_model_and_ocr(input_path, model_json_path, out_json_path=None):
    # load model json
    logging.info("Chargement du modèle JSON : %s", model_json_path)
    with open(model_json_path, "r", encoding="utf-8") as f:
        model = json.load(f)

    logging.debug("DEBUG - JSON chargé : type=%s taille=%s", type(model), len(model) if hasattr(model, "__len__") else "?" )

    # prepare images (if pdf -> convert to images)
    tmpdir = tempfile.mkdtemp(prefix="ocr_tmp_")
    images = ensure_images_from_input(input_path, tmpdir)

    results_all = []

    # iterate over entries in model (each entry normally references an image)
    for entry_index, entry in enumerate(model):
        logging.debug("DEBUG - Analyse entrée JSON id=%s", entry.get("id", entry_index))
        entry_result = {"id": entry.get("id"), "image": entry.get("image"), "ocr": {}}

        # Determine which image to use for this entry:
        # if model contains 'image' path and that file exists -> use it
        image_path = None
        if entry.get("image"):
            candidate = Path(entry["image"])
            if candidate.exists():
                image_path = str(candidate)
            else:
                logging.debug("DEBUG - image path in JSON not found: %s", entry["image"])

        # fallback: use first converted image if available
        if image_path is None:
            if images:
                image_path = images[0]
            else:
                logging.error("No image available to OCR (neither input image nor PDF conversion).")
                entry_result["ocr"]["error"] = "No image available"
                results_all.append(entry_result)
                continue

        # For each top-level zone group (Header, Footer, Table, Document, table_header, line_cells, etc.)
        # on parcourt keys et si c'est une liste de zones on OCR toutes les zones et concatène.
        for key, value in entry.items():
            # skip metadata fields we don't want to OCR
            if key in ("id", "image", "annotator", "annotation_id", "created_at", "updated_at", "lead_time"):
                continue

            # value might be list of zones or existing labelled text fields (header_value etc)
            if isinstance(value, list) and value and isinstance(value[0], dict) and ("x" in value[0] and "y" in value[0]):
                # list of rectangle zones -> OCR each
                texts = []
                logging.debug("DEBUG - Analyse entrée JSON id=%s avec %s zones", entry.get("id"), len(value))
                for zone in value:
                    try:
                        crop_png = crop_region_save(image_path, zone, tmpdir)
                        text = run_tesseract(crop_png, lang="fra")
                        texts.append(text)
                    except Exception as e:
                        logging.exception("Erreur lors du crop/OCR: %s", e)
                        texts.append("")
                # compact join: si tous vides -> ""
                entry_result["ocr"][key] = texts if texts else []
            else:
                # non-zones: peut déjà contenir header_label/header_value/line_value etc.
                # Conservons la valeur telle quelle (mais l'utilisateur voulait OCR > on laissera aussi)
                entry_result["ocr"][key] = value

        # Post-process: convert lists of OCR'd zones into single display strings using safe_value
        display_map = {}
        for champ, val in entry_result["ocr"].items():
            if isinstance(val, list) and val and isinstance(val[0], str):
                # If all empty or spaces => VIDE
                joined = "\n---\n".join([v.strip() for v in val if v is not None])
                # if joined empty -> set to "" (will be converted to VIDE)
                display_map[champ] = joined if joined.strip() != "" else ""
            else:
                display_map[champ] = val

        # Replace None and empty with markers
        final_map = {}
        for champ, val in display_map.items():
            final_map[champ] = safe_value(val)

        entry_result["ocr_final"] = final_map
        results_all.append(entry_result)

    # Print ASCII table summarizing each entry
    for entry in results_all:
        print("\n=== Résultats OCR pour entry id={} image={} ===".format(entry.get("id"), entry.get("image")))
        table_data = []
        # order keys for nicer output: prefer Header, Table, Footer, Document type
        preferred_order = ["header", "header_label", "header_value", "table", "table_header", "line_cells", "line_value", "footer", "footer_label", "footer_value", "Document", "Document type"]
        keys = list(entry["ocr_final"].keys())
        # make ordered list
        ordered_keys = [k for k in preferred_order if k in keys] + [k for k in keys if k not in preferred_order]
        for champ in ordered_keys:
            table_data.append([champ, entry["ocr_final"].get(champ)])
        print(tabulate(table_data, headers=["Champ", "Valeur OCR"], tablefmt="grid"))

    # dump results_all to a json file for later consumption
    if out_json_path is None:
        out_json_path = str(Path(model_json_path).with_name(Path(model_json_path).stem + "_extracted.json"))
    try:
        with open(out_json_path, "w", encoding="utf-8") as f:
            json.dump(results_all, f, ensure_ascii=False, indent=2)
        logging.info("Résultats écrits dans : %s", out_json_path)
    except Exception as e:
        logging.error("Impossible d'écrire le json de sortie: %s", e)

    # cleanup temporary directory? On purpose on laisse pour debug; tu peux supprimer si tu veux
    logging.debug("Tmp dir (left for debug): %s", tmpdir)
    return results_all


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 extract_invoice.py <input_pdf_or_image> <model_json> [<output_json>]")
        sys.exit(1)
    input_path = sys.argv[1]
    model_json = sys.argv[2]
    out_json = sys.argv[3] if len(sys.argv) > 3 else None
    process_model_and_ocr(input_path, model_json, out_json)


if __name__ == "__main__":
    main()
