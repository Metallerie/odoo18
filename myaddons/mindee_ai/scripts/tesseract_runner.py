#!/usr/bin/env python3
import sys
import pytesseract
from pytesseract import Output
from PIL import Image
import fitz  # PyMuPDF
import re
import json
import argparse

# ------------------ OCR ------------------

def ocr_words(image):
    """OCR et retourne une liste de mots avec coordonnées"""
    data = pytesseract.image_to_data(image, output_type=Output.DICT, lang="fra")
    words = []
    for i, txt in enumerate(data["text"]):
        if not txt.strip():
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append({
            "text": txt.strip(),
            "x": x, "y": y, "w": w, "h": h,
            "cx": x + w/2, "cy": y + h/2
        })
    return words

def group_words_into_lines(words, y_thresh=10):
    """Regroupe les mots OCR en lignes selon Y"""
    lines = []
    for w in sorted(words, key=lambda k: k["cy"]):
        placed = False
        for line in lines:
            if abs(line[0]["cy"] - w["cy"]) <= y_thresh:
                line.append(w)
                placed = True
                break
        if not placed:
            lines.append([w])
    # Tri horizontal
    lines = [sorted(l, key=lambda w: w["x"]) for l in lines]
    return lines

def normalize_text(s):
    return s.replace("\n", " ").strip()

def line_text(line):
    return normalize_text(" ".join([w["text"] for w in line]))

# ------------------ HEADER DETECTION ------------------

def find_header_line(lines, min_tokens=2):
    header_idx, best_score = None, -1
    for idx, line in enumerate(lines):
        text = line_text(line).lower()
        score = 0
        for kw in ["désignation", "description", "qté", "prix", "unité", "montant", "total", "tva"]:
            if kw in text:
                score += 1
        tokens = text.split()
        if len(tokens) >= min_tokens and score > best_score:
            best_score = score
            header_idx = idx
    return header_idx, best_score

# ------------------ COLUMN SPLIT ------------------

def header_columns_from_words(header_line, min_gap=40):
    """Déduit colonnes à partir des X des mots de l’en-tête"""
    ws = sorted(header_line, key=lambda w: w["x"])
    if not ws:
        return [], []

    cols = [[ws[0]]]
    for w in ws[1:]:
        gap = w["x"] - (cols[-1][-1]["x"] + cols[-1][-1]["w"])
        if gap > min_gap:
            cols.append([w])
        else:
            cols[-1].append(w)

    labels, cuts = [], []
    for i, col in enumerate(cols):
        col_sorted = sorted(col, key=lambda w: w["x"])
        label = " ".join([w["text"] for w in col_sorted])
        labels.append(label)
        if i < len(cols) - 1:
            right = col_sorted[-1]["x"] + col_sorted[-1]["w"]
            left_next = sorted(cols[i+1], key=lambda w: w["x"])[0]["x"]
            cuts.append((right + left_next) // 2)
    return cuts, labels

def split_by_cuts(line_words, cut_x):
    nb_cols = len(cut_x) + 1
    buckets = [[] for _ in range(nb_cols)]
    for w in sorted(line_words, key=lambda z: z["x"]):
        x = w["x"]
        col = 0
        while col < len(cut_x) and x > cut_x[col]:
            col += 1
        buckets[col].append(w["text"])
    return [" ".join(b).strip() for b in buckets]

# ------------------ TABLE EXTRACTION ------------------

def extract_table(lines, header_idx):
    products, others = [], []
    for l in lines[header_idx+1:]:
        txt = line_text(l)
        if not txt:
            continue
        if re.search(r"(total|net à payer|merci|rcs|iban)", txt.lower()):
            others.append(txt)
        else:
            products.append(l)
    return products, others

# ------------------ MAIN OCR RUNNER ------------------

def run_ocr(pdf_file):
    doc = fitz.open(pdf_file)
    pages_data = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        words = ocr_words(img)
        lines = group_words_into_lines(words)

        lines_data = [{"text": line_text(l), "words": l} for l in lines]
        phrases = [ld["text"] for ld in lines_data if ld["text"]]

        header_idx, score = find_header_line(lines)
        header_text, header_cols, products_struct, others = None, [], [], []
        if header_idx is not None:
            header_line = lines[header_idx]
            header_text = line_text(header_line)

            cut_x, header_cols = header_columns_from_words(header_line)
            products, others = extract_table(lines, header_idx)

            if cut_x:
                for L in products:
                    products_struct.append(split_by_cuts(L, cut_x))
            else:
                # fallback simple : tout en une seule colonne
                for L in products:
                    products_struct.append([line_text(L)])

        # Extraction numéro/date facture (rapide)
        parsed = {}
        for p in phrases:
            m = re.search(r"(facture[^\d]*\d+)", p.lower())
            if m:
                parsed["invoice_number"] = p
            if re.search(r"\d{2}[/-]\d{2}[/-]\d{4}", p):
                parsed["invoice_date"] = re.search(r"\d{2}[/-]\d{2}[/-]\d{4}", p).group()

        pages_data.append({
            "page": page_num + 1,
            "phrases": phrases,
            "parsed": parsed,
            "header_index": header_idx,
            "header_text": header_text,
            "header": header_cols,
            "products": products_struct,
            "others": others
        })
    return {"pages": pages_data}

# ------------------ MAIN ------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="PDF à analyser")
    parser.add_argument("--console", action="store_true", help="Afficher texte brut")
    args = parser.parse_args()

    result = run_ocr(args.file)
    if args.console:
        for page in result["pages"]:
            print("\n".join(page["phrases"]))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
