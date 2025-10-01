# find_table_header.py
# Étape 2 : détecter la ligne d’en-tête et fermer le tableau dès que la structure casse

import sys, io, unicodedata, re
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

# ---------- Utils ----------
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
    s = strip_accents(s).lower()
    s = " ".join(s.split())  # condense espaces
    return s

# ---------- Détection en-tête ----------
HEADER_TOKENS = {
    "ref", "reference", "designation", "desi", "qte", "quantite", "unite",
    "prix", "prix unitaire", "montant", "tva"
}

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

# ---------- Détection lignes produits ----------
def looks_like_product_line(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    has_word = re.search(r"[A-Za-z]", t) is not None
    has_number = re.search(r"\d", t) is not None
    has_price = re.search(r"\d+[.,]\d{2}", t) is not None
    return has_word and (has_number or has_price)

def extract_table(lines, header_idx):
    table = []
    for L in lines[header_idx:]:
        if header_score(L["text"]) > 0:  # en-tête
            table.append(L)
            continue
        if looks_like_product_line(L["text"]):
            table.append(L)
        else:
            break  # on arrête dès que ça ne ressemble plus à une ligne produit
    return table

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

            table_zone = extract_table(lines, idx)
            print("\n   --- Tableau extrait ---")
            for j, L in enumerate(table_zone, start=idx):
                print(f" [{j:>3}] {L['text']}")
