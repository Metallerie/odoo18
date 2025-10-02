# find_table_header.py
# Détection en-tête + extraction lignes produits avec regex par fournisseur

import sys, io, unicodedata, re
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

# ---------- OCR utils ----------
def pdf_to_images(pdf_path, dpi=200):
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

# ---------- Regex par fournisseur ----------
REGEX_PATTERNS = {
    "CCL": re.compile(r"^([A-Z0-9\-]{3,})\s+(.+?)\s+(\d+(?:[.,]\d+)?)\s?(PI|KG|ML|M2|U|L)?\s+(\d+[.,]\d{2})\s+(\d+[.,]\d{2})(?:\s+(\d+%?))?$"),
    "LAMESCIE": re.compile(r"^([A-Z0-9\-]{5,})\s+(.+?)\s+(\d{1,3}\s?%)\s+(\d+[.,]\d{2})\s*€?\s+(\d+)\s+(\d+[.,]\d{2})"),
    "LEB": re.compile(r"^(.+?)\s+(\d+[.,]\d{2})€?\s+(\d+%?)\s+(\d+[.,]\d{2})€?$"),
    "FREE": re.compile(r"^Total\s+(\d+[.,]\d{2})€?\s+(\d+[.,]\d{2})€?$"),
    "EDF": re.compile(r"^(.+?)\s+(\d+[.,]\d{2})€?$"),
    "PROLIANS": re.compile(r"^([A-Z0-9\-]{4,})\s+(.+?)\s+(\d+[.,]\d{2})\s+(\d+[.,]\d{2})$")
}

def detect_supplier(text: str) -> str:
    t = norm(text)
    if "ccl" in t:
        return "CCL"
    if "lame scie" in t or "ruban" in t:
        return "LAMESCIE"
    if "leb" in t:
        return "LEB"
    if "free" in t:
        return "FREE"
    if "edf" in t:
        return "EDF"
    if "prolians" in t:
        return "PROLIANS"
    return "CCL"  # fallback

# ---------- Fusion spéciale Prolians ----------
def merge_lines_for_prolians(lines):
    merged = []
    skip = False
    for i in range(len(lines)):
        if skip:
            skip = False
            continue
        if i < len(lines)-1:
            cur, nxt = lines[i]["text"], lines[i+1]["text"]
            # ligne désignation suivie d'une ligne code/prix
            if (re.search(r"[A-Za-z]", cur) and not re.search(r"\d+[.,]\d{2}", cur)) and re.search(r"\d+[.,]\d{2}", nxt):
                merged.append({"text": nxt.split()[0] + " " + cur + " " + " ".join(nxt.split()[1:])})
                skip = True
                continue
        merged.append(lines[i])
    return merged

# ---------- Extraction ----------
def extract_table(lines, header_idx, supplier):
    table = []
    regex = REGEX_PATTERNS.get(supplier)
    if supplier == "PROLIANS":
        lines = merge_lines_for_prolians(lines[header_idx:])
    else:
        lines = lines[header_idx:]
    for L in lines:
        txt = L["text"]
        if header_score(txt) > 0:  
            continue
        if is_footer_line(txt):
            break
        if regex and regex.match(txt):
            table.append(txt)
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
            supplier = detect_supplier(" ".join(l["text"] for l in lines[:10]))
            print(f"✅ Fournisseur détecté : {supplier}")
            print(f"✅ En-tête trouvé (score={score}) à l’index {idx}: {lines[idx]['text']}")

            table = extract_table(lines, idx, supplier)
            print("\n   --- Produits détectés ---")
            for t in table:
                print("   •", t)
