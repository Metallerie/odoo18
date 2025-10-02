# find_table_header.py
# Détection en-tête + distinction lignes produit / autres

import sys, io, unicodedata, re
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

# ---------- OCR utils ----------
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
        words.append({"text": txt, "x": x, "y": y, "cx": x + w/2, "cy": y + h/2})
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

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def norm(s: str) -> str:
    return " ".join(strip_accents(s).lower().split())

# ---------- Header detection ----------
HEADER_TOKENS = {
    "ref", "reference", "designation", "desi", "qte", "quantite", "unite",
    "prix", "prix unitaire", "montant", "tva", "article", "description"
}

FOOTER_TOKENS = {"total ht", "total ttc", "net a payer"}

def header_score(text: str) -> int:
    t = norm(text)
    return sum(1 for tok in HEADER_TOKENS if tok in t)

def find_header_line(lines, min_tokens=2):
    best_idx, best_score = None, 0
    for i, L in enumerate(lines):
        sc = header_score(L["text"])
        if sc > best_score:
            best_score, best_idx = sc, i
    if best_idx is not None and best_score >= min_tokens:
        return best_idx, best_score
    return None, 0

def is_footer_line(text: str) -> bool:
    t = norm(text)
    return any(tok in t for tok in FOOTER_TOKENS)

# ---------- Product line check ----------
def is_product_line(text: str) -> bool:
    """Heuristique pour détecter une ligne produit"""
    t = text.strip()
    if not t:
        return False

    # doit contenir lettres + chiffres
    has_word = re.search(r"[A-Za-z]", t) is not None
    has_number = re.search(r"\d", t) is not None

    # contient un prix avec décimales
    has_price = re.search(r"\d+[.,]\d{2}", t) is not None

    # contient une unité typique
    has_unit = re.search(r"\b(PI|ML|KG|M2|U|L)\b", t.upper()) is not None

    # longueur minimale
    long_enough = len(t.split()) >= 3

    return (has_word and has_number and (has_price or has_unit) and long_enough)

def extract_table(lines, header_idx):
    products, others = [], []
    for L in lines[header_idx:]:
        if header_score(L["text"]) > 0:  # garder l'en-tête
            others.append(L)
            continue
        if is_footer_line(L["text"]):
            break
        if is_product_line(L["text"]):
            products.append(L)
        else:
            others.append(L)
    return products, others

# ---------- Main ----------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 find_table_header.py <facture.pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    pages = pdf_to_images(pdf_path)

    for pageno, img in enumerate(pages, start=1):
        words = ocr_words(img)
        lines = group_into_lines(words)

        idx, score = find_header_line(lines, min_tokens=2)

        print(f"\n📄 Page {pageno}")
        if idx is None:
            print("❌ Aucun en-tête détecté.")
        else:
            print(f"✅ En-tête trouvé (score={score}) à l’index {idx}:")
            print(f"   {lines[idx]['text']}")

            products, others = extract_table(lines, idx)

            print("\n   --- Produits détectés ---")
            for L in products:
                print("   •", L["text"])

            print("\n   --- Autres lignes ---")
            for L in others:
                print("   •", L["text"])
