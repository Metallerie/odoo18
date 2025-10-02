#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import json
import re
import unicodedata
import argparse
from pdf2image import convert_from_path
import pytesseract

# ---------------- Utils: normalisation ----------------

def normalize_text(s: str) -> str:
    """Normalise apostrophes et espaces (garde les accents pour l'affichage)."""
    if not s:
        return ""
    s = s.replace("\u2019", "'")   # ’ -> '
    s = s.replace("\u00A0", " ")   # NBSP -> espace
    s = re.sub(r"\s+", " ", s).strip()
    return s

def fold_for_match(s: str) -> str:
    """Retourne une version minuscule et sans accents pour les comparaisons/regex."""
    if not s:
        return ""
    s = normalize_text(s)
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()

# ---------------- Fusion lignes (ex: "Facture n°" + "2025/1680") ----------------

def merge_invoice_number_phrases(phrases):
    merged = []
    skip_next = False
    keywords = [fold_for_match(k) for k in [
        "facture", "facture n°", "facture numero", "facture no",
        "facture d'acompte", "facture d’acompte",
        "facture d'acompte n°", "facture d’acompte n°"
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

# ---------------- Extraction ----------------

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

# ---------------- OCR principal ----------------

def run_ocr(pdf_path):
    pages_data = []
    images = convert_from_path(pdf_path)
    for idx, img in enumerate(images, start=1):
        text = pytesseract.image_to_string(img, lang="fra")
        phrases = [normalize_text(p) for p in text.split("\n") if normalize_text(p)]
        phrases = merge_invoice_number_phrases(phrases)
        parsed = extract_invoice_data(phrases)
        # TODO: à améliorer -> détection tableau produits
        pages_data.append({
            "page": idx,
            "content": text,
            "phrases": phrases,
            "parsed": parsed,
            "products": [p for p in phrases if re.search(r"\d+[.,]\d{2}", p)]  # heuristique simpliste
        })
    return {"pages": pages_data}

# ---------------- CLI ----------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_file", help="Chemin vers le fichier PDF")
    parser.add_argument("--console", action="store_true", help="Mode console : résumé lisible")
    args = parser.parse_args()

    if not os.path.exists(args.pdf_file):
        print(json.dumps({"error": f"File not found: {args.pdf_file}"}))
        sys.exit(1)

    try:
        result = run_ocr(args.pdf_file)
        if args.console:
            for page in result["pages"]:
                print(f"\n📄 Page {page['page']}")
                if page["parsed"].get("invoice_number"):
                    print("✅ Numéro :", page["parsed"]["invoice_number"])
                if page["parsed"].get("invoice_date"):
                    print("✅ Date   :", page["parsed"]["invoice_date"])
                if page.get("products"):
                    print("✅ Produits détectés :")
                    for p in page["products"]:
                        print("   •", p)
            print("\n--- JSON complet disponible si besoin ---")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
