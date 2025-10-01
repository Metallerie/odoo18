# find_table_header.py
# Étape 1 : lire le PDF, OCR, regrouper en lignes, trouver la ligne d’en-tête du tableau.

import sys, io, unicodedata
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

# ---------- Utils ----------
def pdf_to_images(pdf_path, dpi=300):
    doc = fitz.open(pdf_path)
    pages = []
    for p in doc:
        pix = p.get_pixmap(dpi=dpi)
        pages.append(Image.open(io.BytesIO(pix.tobytes("png"))))
    return pages

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
    # texte par ligne (ordre gauche→droite)
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

# Tokens d’en-tête (on cherche au moins 2 dans la même ligne)
HEADER_TOKENS = {
    "ref", "reference", "designation", "desi", "qte", "quantite", "unite",
    "prix", "prix unitaire", "montant", "tva"
}

def header_score(text: str) -> int:
    t = norm(text)
    score = 0
    for tok in HEADER_TOKENS:
        if tok in t:
            score += 1
    return score

def find_header_line(lines, min_tokens=2):
    best_idx, best_score = None, 0
    for i, L in enumerate(lines):
        sc = header_score(L["text"])
        if sc > best_score:
            best_score, best_idx = sc, i
    if best_idx is not None and best_score >= min_tokens:
        return best_idx, best_score
    return None, 0

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
            # Top 5 candidats pour debug
            candidates = sorted(
                [(i, header_score(L['text']), L['text']) for i, L in enumerate(lines)],
                key=lambda x: x[1], reverse=True
            )[:5]
            for i, sc, txt in candidates:
                print(f"  ? score={sc:>2} | idx={i:>3} | {txt}")
        else:
            print(f"✅ En-tête trouvé (score={score}) à l’index {idx}:")
            print(f"   {lines[idx]['text']}")
            # Contexte visuel ±3 lignes
            start = max(0, idx-3)
            end = min(len(lines), idx+4)
            print("\n   --- Contexte ---")
            for j in range(start, end):
                mark = "→" if j == idx else " "
                print(f" {mark} [{j:>3}] {lines[j]['text']}")
