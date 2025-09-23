#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, os, json, re, unicodedata
from pdf2image import convert_from_path
import pytesseract

# ---------------- Utils ----------------
def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\u2019", "'").replace("\u00A0", " ")
    return re.sub(r"\s+", " ", s).strip()

def fold_for_match(s: str) -> str:
    if not s:
        return ""
    s = normalize_text(s)
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()

# ---------------- OCR mots ----------------
def ocr_words(pdf_path):
    images = convert_from_path(pdf_path)
    pages = []
    for img in images:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, lang="fra")
        words = []
        for i, txt in enumerate(data["text"]):
            if txt.strip():
                words.append({
                    "text": normalize_text(txt),
                    "left": data["left"][i],
                    "top": data["top"][i],
                    "width": data["width"][i],
                    "height": data["height"][i]
                })
        pages.append(words)
    return pages

# ---------------- Reconstruction par lignes ----------------
def group_words_into_lines(words, y_thresh=10):
    lines, current_line = [], []
    sorted_words = sorted(words, key=lambda w: (w["top"], w["left"]))
    current_y = None
    for w in sorted_words:
        if current_y is None or abs(w["top"] - current_y) <= y_thresh:
            current_line.append(w)
            if current_y is None:
                current_y = w["top"]
        else:
            lines.append(current_line)
            current_line = [w]
            current_y = w["top"]
    if current_line:
        lines.append(current_line)
    return lines

def line_to_text(line):
    return " ".join(sorted([w["text"] for w in line], key=lambda x: x))

# ---------------- Extraction tableau ----------------
def extract_table(words):
    lines = group_words_into_lines(words)
    headers, bounds = [], []

    # Cherche l'entête
    for line in lines:
        line_txt = " ".join(w["text"] for w in line).lower()
        if "réf" in line_txt and "désignation" in line_txt:
            headers = [w["text"] for w in line]
            bounds = [w["left"] for w in line] + [line[-1]["left"] + line[-1]["width"]]
            break

    if not headers:
        return [], []

    # Associe chaque ligne aux colonnes
    rows = []
    for line in lines:
        row = {h: "" for h in headers}
        for w in line:
            for i, h in enumerate(headers):
                if i < len(bounds)-1 and bounds[i] <= w["left"] < bounds[i+1]:
                    row[h] += " " + w["text"]
                    break
        if any(v.strip() for v in row.values()):
            rows.append({k: v.strip() for k, v in row.items()})

    return headers, rows

# ---------------- Main ----------------
def run(pdf_path):
    pages_words = ocr_words(pdf_path)
    result = {"pages": []}
    for i, words in enumerate(pages_words, 1):
        headers, rows = extract_table(words)
        result["pages"].append({
            "page": i,
            "headers": headers,
            "products": rows
        })
    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tesseract_runner2.py <file.pdf>")
        sys.exit(1)

    pdf = sys.argv[1]
    if not os.path.exists(pdf):
        print(json.dumps({"error": "file not found"}))
        sys.exit(1)

    print(json.dumps(run(pdf), indent=2, ensure_ascii=False))
