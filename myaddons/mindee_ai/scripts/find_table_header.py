# find_table_header.py
# Étape 4 : détecter en-tête, isoler tableau, clusteriser les colonnes

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

# ---------- Product line check ----------
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
            break
    return table

# ---------- Column clustering ----------
def cluster_columns(xs, tol=50):
    """Regroupe les X proches dans la même colonne"""
    xs = sorted(xs)
    clusters = []
    for x in xs:
        if not clusters:
            clusters.append([x])
        elif abs(x - sum(clusters[-1]) / len(clusters[-1])) <= tol:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return [int(sum(c) / len(c)) for c in clusters]

def detect_columns(lines, tol=50, max_cols=8):
    xs = []
    for L in lines:
        for w in L["words"]:
            xs.append(w["x"])
    if not xs:
        return []
    clusters = cluster_columns(xs, tol=tol)
    # réduire si trop de colonnes
    if len(clusters) > max_cols:
        merged = []
        for x in clusters:
            if not merged or abs(x - merged[-1]) > tol:
                merged.append(x)
        clusters = merged
    return clusters

def assign_to_columns(line, col_positions):
    cells = {i: [] for i in range(len(col_positions))}
    for w in line["words"]:
        idx = min(range(len(col_positions)), key=lambda i: abs(w["x"] - col_positions[i]))
        cells[idx].append(w["text"])
    return [" ".join(cells[i]) for i in range(len(col_positions))]

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

            # extraire bloc tableau
            table_zone = extract_table(lines, idx)

            # détecter colonnes avec clustering
            col_positions = detect_columns(table_zone, tol=50, max_cols=8)
            print(f"\n   Colonnes détectées ({len(col_positions)}): {col_positions}")

            print("\n   --- Tableau structuré ---")
            for L in table_zone:
                cells = assign_to_columns(L, col_positions) if col_positions else [L["text"]]
                print(" | ".join(cells))
