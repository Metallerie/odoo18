#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, os, io, json, re, unicodedata, argparse
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

# ---------------- Normalisation ----------------
def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\u2019", "'").replace("\u00A0", " ")
    return re.sub(r"\s+", " ", s).strip()

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def norm(s: str) -> str:
    return " ".join(strip_accents((s or "")).lower().split())

# ---------------- OCR mots -> lignes ----------------
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
        L["text"] = normalize_text(" ".join(a["text"] for a in L["words"]))
    return lines

# ---------------- Début/Fin tableau ----------------
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

# ---------------- Split colonnes ----------------
def split_cols(text, header_text=None):
    """Découpe une ligne de tableau en colonnes."""
    sep = r"\s{2,}"  # par défaut = au moins 2 espaces
    if header_text and "|" in header_text:
        sep = r"\|"  # si l'entête contient des pipes
    return [col.strip() for col in re.split(sep, text) if col.strip()]

# ---------------- Heuristique produit ----------------
def is_product_line(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    has_word   = re.search(r"[A-Za-z]", t) is not None
    has_number = re.search(r"\d", t) is not None
    has_price  = re.search(r"\d+[.,]\d{2}", t) is not None
    has_unit   = re.search(r"\b(PI|ML|KG|M2|U|L)\b", t.upper()) is not None
    long_enough = len(t.split()) >= 3
    if re.search(r"\b(total|net.?a.?payer|somme.?a.?payer)\b", norm(t)):
        return False
    return has_word and has_number and (has_price or has_unit) and long_enough

def extract_table(lines, header_idx):
    products, others = [], []
    for L in lines[header_idx:]:
        txt = L["text"]
        if header_score(txt) > 0:
            others.append(L)
            continue
        if is_footer_line(txt):
            break
        if is_product_line(txt):
            products.append(L)
        else:
            others.append(L)
    return products, others

# ---------------- N° facture + Date ----------------
def merge_invoice_number_phrases(phrases):
    merged, skip = [], False
    keywords = [norm(k) for k in [
        "facture", "facture n°", "facture numero", "facture no",
        "facture d'acompte", "facture d’acompte",
        "facture d'acompte n°", "facture d’acompte n°"
    ]]
    for i, raw in enumerate(phrases):
        if skip:
            skip = False
        else:
            cur = normalize_text(raw); cur_fold = norm(cur)
            if any(k in cur_fold for k in keywords) and i + 1 < len(phrases):
                nxt = normalize_text(phrases[i+1])
                if re.match(r"^[A-Za-z0-9][A-Za-z0-9/\-]*$", nxt):
                    merged.append(f"{cur} {nxt}")
                    skip = True
                    continue
            merged.append(cur)
    return merged

def extract_invoice_data(phrases):
    data = {}
    pat_after_n_label = re.compile(
        r"(?:facture)\s*(?:d'?acompte)?\s*(?:n[°ºo]|no|nº)\s*([A-Za-z0-9][A-Za-z0-9/\-]*)",
        re.IGNORECASE
    )
    pat_after_facture = re.compile(
        r"(?:facture)(?:\s+d'?acompte)?\s+([A-Za-z0-9][A-Za-z0-9/\-]*\d[A-Za-z0-9/\-]*)",
        re.IGNORECASE
    )
    pat_date = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")
    for raw in phrases:
        phrase = normalize_text(raw)
        folded = norm(phrase)
        if "facture" in folded:
            m = pat_after_n_label.search(folded)
            if m and "invoice_number" not in data:
                data["invoice_number"] = m.group(1)
            if "invoice_number" not in data:
                m2 = pat_after_facture.search(folded)
                if m2:
                    data["invoice_number"] = m2.group(1)
        if "invoice_date" not in data:
            mdate = pat_date.search(phrase)
            if mdate:
                data["invoice_date"] = mdate.group(1)
    return data

# ---------------- OCR principal ----------------
def run_ocr(pdf_path, dpi=300):
    pages = convert_from_path(pdf_path, dpi=dpi)
    out = {"pages": []}

    for idx, img in enumerate(pages, start=1):
        words = ocr_words(img)
        lines = group_into_lines(words)
        line_texts = [L["text"] for L in lines]

        phrases = merge_invoice_number_phrases(line_texts)
        parsed = extract_invoice_data(phrases)

        header_idx, score = find_header_line(lines, min_tokens=2)
        products, others = [], []
        header_text, header_cols, products_struct = None, [], []
        if header_idx is not None:
            header_text = lines[header_idx]["text"]
            header_cols = split_cols(header_text)
            products, others = extract_table(lines, header_idx)
            for L in products:
                products_struct.append(split_cols(L["text"], header_text))

        out["pages"].append({
            "page": idx,
            "phrases": phrases,
            "parsed": parsed,
            "header_index": header_idx,
            "header_text": header_text,
            "header": header_cols,
            "products": products_struct,
            "others": [L["text"] for L in others],
        })

    return out

# ---------------- CLI ----------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_file", help="Chemin du PDF")
    ap.add_argument("--console", action="store_true", help="Affichage lisible dans le terminal")
    ap.add_argument("--dpi", type=int, default=300, help="Résolution OCR (par défaut 300)")
    args = ap.parse_args()

    if not os.path.exists(args.pdf_file):
        print(json.dumps({"error": f"File not found: {args.pdf_file}"}))
        sys.exit(1)

    try:
        result = run_ocr(args.pdf_file, dpi=args.dpi)
        if args.console:
            for p in result["pages"]:
                print(f"\n📄 Page {p['page']}")
                if p["header_text"]:
                    print("✅ En-tête :", p["header_text"])
                    print("   Colonnes:", p["header"])
                if p["parsed"].get("invoice_number"):
                    print("   Numéro  :", p["parsed"]["invoice_number"])
                if p["parsed"].get("invoice_date"):
                    print("   Date    :", p["parsed"]["invoice_date"])
                print("\n   --- Produits détectés ---")
                for row in p["products"]:
                    print("   •", row)
                if not p["products"]:
                    print("   (aucun)")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
