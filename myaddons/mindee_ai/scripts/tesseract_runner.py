#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json
import re
from pdf2image import convert_from_path
import pytesseract

# ---------- 🔧 Fonctions utilitaires ----------------

def merge_invoice_number_phrases(phrases):
    merged = []
    skip_next = False
    invoice_keywords = [
        "facture",
        "facture d'acompte",
        "facture n°",
        "facture d’acompte",
        "facture numero",
        "facture no",
    ]
    for i, phrase in enumerate(phrases):
        if skip_next:
            skip_next = False
            continue
        lower_phrase = phrase.lower()
        if any(k in lower_phrase for k in invoice_keywords) and i + 1 < len(phrases):
            next_phrase = phrases[i + 1].strip()
            if re.match(r"^[A-Za-z0-9/\-]+$", next_phrase):
                merged_phrase = f"{phrase.strip()} {next_phrase}"
                merged.append(merged_phrase)
                skip_next = True
                continue
        merged.append(phrase)
    return merged


def extract_invoice_data(phrases):
    data = {}
    invoice_patterns = [r"facture\s*(?:d['’]acompte)?\s*[n°:\-]?\s*([A-Za-z0-9/\-]+)"]
    date_patterns = [r"(\d{2}[/-]\d{2}[/-]\d{4})"]  # 17/09/2025 ou 17-09-2025
    for phrase in phrases:
        for pat in invoice_patterns:
            m = re.search(pat, phrase, flags=re.IGNORECASE)
            if m:
                data["invoice_number"] = m.group(1)
                break
        for pat in date_patterns:
            m = re.search(pat, phrase)
            if m:
                data["invoice_date"] = m.group(1)
                break
    return data


# ---------- 🔧 Extraction du tableau ----------------

def detect_table_headers(phrases):
    headers = []
    for phrase in phrases:
        low = phrase.lower()
        if any(k in low for k in ["réf", "reference", "référence", "code", "article n°"]):
            headers.append("ref")
        if any(k in low for k in ["désignation", "article", "produit"]):
            headers.append("description")
        if any(k in low for k in ["qté", "quantité"]):
            headers.append("quantity")
        if any(k in low for k in ["pu", "prix unitaire", "prix unit."]):
            headers.append("unit_price")
        if any(k in low for k in ["total ht", "net ht"]):
            headers.append("total_ht")
        if any(k in low for k in ["tva", "%"]):
            headers.append("tva")
        if any(k in low for k in ["total", "montant", "ttc"]):
            headers.append("total")
    return list(set(headers))


def extract_invoice_lines(phrases):
    headers = detect_table_headers(phrases)
    lines = []
    in_table = False

    for phrase in phrases:
        if any(h in phrase.lower() for h in ["réf", "désignation", "qté", "quantité", "prix", "montant", "tva"]):
            in_table = True
            continue

        if in_table:
            parts = phrase.split()
            nums = [p for p in parts if any(c.isdigit() for c in p) or "%" in p]

            if len(nums) >= 2:
                line = {}
                try:
                    # ✅ REF si alphanumérique en 1er élément
                    if "ref" in headers and re.match(r"^[A-Za-z0-9\-]+$", parts[0]):
                        line["ref"] = parts[0]
                        parts = parts[1:]  # on retire la ref

                    # ✅ Quantité
                    if "quantity" in headers:
                        for p in parts:
                            if re.match(r"^\d+([.,]\d+)?$", p):
                                line["quantity"] = float(p.replace(",", "."))
                                break

                    # ✅ Prix unitaire
                    if "unit_price" in headers:
                        for p in parts:
                            if re.match(r"^\d+([.,]\d+)?$", p):
                                val = float(p.replace(",", "."))
                                if val > 0:
                                    line["unit_price"] = val
                                    break

                    # ✅ TVA (%)
                    if "tva" in headers:
                        for p in parts:
                            if "%" in p:
                                line["tva"] = p.replace(",", ".")
                                break

                    # ✅ Total HT
                    if "total_ht" in headers:
                        match = [p for p in parts if re.match(r"^\d+([.,]\d+)?$", p)]
                        if match:
                            line["total_ht"] = float(match[-1].replace(",", "."))

                    # ✅ Total TTC / général
                    if "total" in headers:
                        match = [p for p in parts if re.match(r"^\d+([.,]\d+)?$", p)]
                        if match:
                            line["total"] = float(match[-1].replace(",", "."))
                except Exception:
                    continue

                # ✅ Description = tout sauf les nombres / pourcentages
                desc = " ".join([p for p in parts if not re.match(r"^[0-9\.,%]+$", p)])
                line["description"] = desc

                lines.append(line)

    return {"headers": headers, "lines": lines}


# ---------- 🔧 OCR principal ----------------

def run_ocr(pdf_path):
    pages_data = []
    images = convert_from_path(pdf_path)

    for idx, img in enumerate(images, start=1):
        text = pytesseract.image_to_string(img, lang="fra")

        phrases = [p.strip() for p in text.split("\n") if p.strip()]
        phrases = merge_invoice_number_phrases(phrases)

        parsed = extract_invoice_data(phrases)
        table = extract_invoice_lines(phrases)

        pages_data.append({
            "page": idx,
            "content": text,
            "phrases": phrases,
            "parsed": parsed,
            "table": table,
        })

    return {"pages": pages_data}


# ---------- 🔧 Exécution CLI ----------------

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
