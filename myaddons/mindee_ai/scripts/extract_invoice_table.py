# extract_invoice_table.py
import sys
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import re

# -------- OCR utilitaires --------
def pdf_to_images(pdf_path, dpi=300):
    """Convertit chaque page PDF en image PIL"""
    doc = fitz.open(pdf_path)
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images.append(img)
    return images

def ocr_image(img):
    """OCR Tesseract avec bbox"""
    data = pytesseract.image_to_data(img, lang="fra", output_type=pytesseract.Output.DICT)
    lines = []
    for i in range(len(data["text"])):
        if not data["text"][i].strip():
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        lines.append({
            "text": data["text"][i],
            "bbox": [x, y, x+w, y+h],
            "y": y + h/2
        })
    return lines

def group_words_into_lines(words, y_thresh=10):
    """Regroupe les mots OCR par ligne (selon la coordonnée Y)"""
    lines = []
    for w in sorted(words, key=lambda x: x["y"]):
        placed = False
        for line in lines:
            if abs(line["y"] - w["y"]) <= y_thresh:
                line["words"].append(w)
                line["y"] = sum(x["y"] for x in line["words"]) / len(line["words"])
                placed = True
                break
        if not placed:
            lines.append({"y": w["y"], "words": [w]})
    # concat texte
    for l in lines:
        l["text"] = " ".join(x["text"] for x in sorted(l["words"], key=lambda x: x["bbox"][0]))
    return lines

# -------- Détection tableau --------
HEADER_KEYS = ["désignation", "réf", "qté", "quantité", "prix", "montant"]
FOOTER_KEYS = ["total", "tva", "net à payer", "ttc"]

def detect_table_zone(lines):
    y_min, y_max = None, None
    for ln in lines:
        t = ln["text"].lower()
        if any(k in t for k in HEADER_KEYS):
            y_min = ln["y"]
        if any(k in t for k in FOOTER_KEYS):
            y_max = ln["y"]
    if y_min is None:
        y_min = min(l["y"] for l in lines)
    if y_max is None:
        y_max = max(l["y"] for l in lines)
    return y_min, y_max

def filter_table_lines(lines):
    y_min, y_max = detect_table_zone(lines)
    return [l for l in lines if y_min <= l["y"] <= y_max]

# -------- MAIN --------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 extract_invoice_table.py <facture.pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    pages = pdf_to_images(pdf_path)
    for i, img in enumerate(pages, 1):
        words = ocr_image(img)
        lines = group_words_into_lines(words)
        table_lines = filter_table_lines(lines)

        print(f"\n📄 --- Page {i} ---")
        for ln in table_lines:
            print("TABLE >>", ln["text"])
    for i, img in enumerate(pages, 1):
        words = ocr_image(img)
        lines = group_words_into_lines(words)

        print(f"\n--- OCR complet page {i} ---")
        for ln in lines:
            print(f"OCR >> {ln['text']}")

        table_lines = filter_table_lines(lines)

        print(f"\n📄 --- Table page {i} ---")
        for ln in table_lines:
            print("TABLE >>", ln["text"])
