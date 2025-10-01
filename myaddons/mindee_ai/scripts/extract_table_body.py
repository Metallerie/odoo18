# extract_table_body.py
# Etape 2 : garder uniquement la zone tableau entre l'en-tête et le pied

import sys, io, unicodedata
import fitz
import pytesseract
from PIL import Image

HEADER_TOKENS = {"ref", "reference", "designation", "desi", "qte", "quantite", "unite",
                 "prix", "prix unitaire", "montant", "tva"}
FOOTER_TOKENS = {"total", "tva", "net"}

def pdf_to_images(pdf_path, dpi=300):
    doc = fitz.open(pdf_path)
    return [Image.open(io.BytesIO(p.get_pixmap(dpi=dpi).tobytes("png"))) for p in doc]

def ocr_words(img):
    d = pytesseract.image_to_data(img, lang="fra", output_type=pytesseract.Output.DICT)
    words = []
    for i in range(len(d["text"])):
        txt = (d["text"][i] or "").strip()
        if not txt: 
            continue
        x, y, w, h = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
        words.append({"text": txt, "x": x, "y": y, "cy": y + h/2})
    return words

def group_into_lines(words, y_thresh=10):
    lines = []
    for w in sorted(words, key=lambda a: a["cy"]):
        placed = False
        for L in lines:
            if abs(L["cy"] - w["cy"]) <= y_thresh:
                L["words"].append(w)
                L["cy"] = sum(z["cy"] for z in L["words"]) / len(L["words"])
                placed = True
                break
        if not placed:
            lines.append({"cy": w["cy"], "words": [w]})
    for L in lines:
        L["words"].sort(key=lambda a: a["x"])
        L["text"] = " ".join(a["text"] for a in L["words"]).strip()
    return lines

def strip_accents(s): 
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def norm(s): 
    return " ".join(strip_accents(s).lower().split())

def contains_token(text, token_set):
    t = norm(text)
    return any(tok in t for tok in token_set)

def extract_table(lines):
    start, end = None, None
    for i, L in enumerate(lines):
        if contains_token(L["text"], HEADER_TOKENS):
            start = i
            break
    for j in range(start+1 if start is not None else 0, len(lines)):
        if contains_token(lines[j]["text"], FOOTER_TOKENS):
            end = j
            break
    if start is None:
        return []
    if end is None:
        end = len(lines)
    return lines[start:end]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 extract_table_body.py <facture.pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    for pageno, img in enumerate(pdf_to_images(pdf_path), start=1):
        lines = group_into_lines(ocr_words(img))
        table = extract_table(lines)

        print(f"\n📄 Page {pageno} — Tableau extrait")
        for L in table:
            print("TABLE >>", L["text"])
