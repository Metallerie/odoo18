#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import json
import re
import io
import unicodedata
from pdf2image import convert_from_path
import pytesseract
import fitz  # PyMuPDF
from PIL import Image

# ---------------- Utils: normalisation ----------------

def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\u2019", "'")   # ’ -> '
    s = s.replace("\u00A0", " ")   # NBSP -> espace
    s = re.sub(r"\s+", " ", s).strip()
    return s

def fold_for_match(s: str) -> str:
    if not s:
        return ""
    s = normalize_text(s)
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def norm(s: str) -> str:
    return " ".join(strip_accents(s).lower().split())

# ---------------- Fusion lignes (ex: "Facture n°" + "2025/1680") ----------------

def merge_invoice_number_phrases(phrases):
    merged = []
    skip_next = False
    keywords = [fold_for_match(k) for k in [
        "facture", "facture n°", "facture numero", "facture no",
        "facture d'acompte", "facture d’acompte",
        "facture d'acompte n°", "facture d’acompte n°",
    ]]
    for i, raw in enumerate(phrases):
        if skip_next:
            skip_next = False
            continue
        cur = normalize_text(raw)
        cur_fold = fold_for_match(cur)
        if any(k in cur_fold for k in keywords) and i + 1 < len(phrases):
            nxt = normalize_text(phrases[i + 1])
            if re.match(r"^[A-Za-z0-9][A-Za-z0-9/\-]*$", nxt):
                merged.append(f"{cur} {nxt}")
                skip_next = True
                continue
        merged.append(cur)
    return merged

# ---------------- Extraction numéro/date ----------------

def extract_invoice_data(phrases):
    data = {}
    pat_after_n_label = re.compile(
        r"(?:facture)\s*(?:d'?acompte)?\s*(?:n[°ºo]|no|nº)\s*([A-Za-z0-9][A-Za-z0-9/\-]*)",
        flags=re.IGNORECASE
    )
    pat_after_facture = re.compile(
        r"(?:facture)(?:\s+d'?acompte)?\s+([A-Za-z0-9][A-Za-z0-9/\-]*\d[A-Za-z0-9/\-]*)",
        flags=re.IGNORECASE
    )
    pat_date = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")
    for raw in phrases:
        phrase = normalize_text(raw)
        folded = fold_for_match(phrase)
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

# ---------------- Table header & product lines ----------------

HEADER_TOKENS = {"ref","reference","designation","desi","qte","quantite","unite","prix","prix unitaire","montant","tva","article","description"}
FOOTER_TOKENS = {"total ht","total ttc","net a payer"}

def header_score(text: str) -> int:
    t = norm(text)
    return sum(1 for tok in HEADER_TOKENS if tok in t)

def find_header_line(lines, min_tokens=2):
    best_idx, best_score = None, 0
    for i, L in enumerate(lines):
        sc = header_score(L)
        if sc > best_score:
            best_score, best_idx = sc, i
    if best_idx is not None and best_score >= min_tokens:
        return best_idx, best_score
    return None, 0

def is_footer_line(text: str) -> bool:
    t = norm(text)
    return any(tok in t for tok in FOOTER_TOKENS)

def is_product_line(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    has_word = re.search(r"[A-Za-z]", t) is not None
    has_number = re.search(r"\d", t) is not None
    has_price = re.search(r"\d+[.,]\d{2}", t) is not None
    has_unit = re.search(r"\b(PI|ML|KG|M2|U|L)\b", t.upper()) is not None
    long_enough = len(t.split()) >= 3
    return (has_word and has_number and (has_price or has_unit) and long_enough)

def extract_table(phrases, header_idx):
    products, others = [], []
    for L in phrases[header_idx:]:
        if header_score(L) > 0:
            others.append(L)
            continue
        if is_footer_line(L):
            break
        if is_product_line(L):
            products.append(L)
        else:
            others.append(L)
    return products, others

# ---------------- OCR principal ----------------

def run_ocr(pdf_path):
    pages_data = []
    images = convert_from_path(pdf_path)
    for idx, img in enumerate(images, start=1):
        text = pytesseract.image_to_string(img, lang="fra")
        phrases = [normalize_text(p) for p in text.split("\n") if normalize_text(p)]
        phrases = merge_invoice_number_phrases(phrases)
        parsed = extract_invoice_data(phrases)
        header_idx, score = find_header_line(phrases, min_tokens=2)
        products, others = [], []
        if header_idx is not None:
            products, others = extract_table(phrases, header_idx)
        pages_data.append({
            "page": idx,
            "content": text,
            "phrases": phrases,
            "parsed": parsed,
            "header_index": header_idx,
            "products": products,
            "others": others
        })
    return {"pages": pages_data}

# ---------------- CLI ----------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tesseract_runner.py <pdf_file>")
        sys.exit(1)
    pdf_file = sys.argv[1]
    if not os.path.exists(pdf_file):
        print(json.dumps({"error": f"File not found: {pdf_file}"}))
        sys.exit(1)
    try:
        result = run_ocr(pdf_file)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
