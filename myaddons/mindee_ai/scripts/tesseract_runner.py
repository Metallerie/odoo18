#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import re
from pdf2image import convert_from_path
import pytesseract
import pandas as pd


# ---------- 🔧 OCR avec coordonnées ----------------

def extract_words_with_positions(image):
    df = pytesseract.image_to_data(image, lang="fra", output_type=pytesseract.Output.DATAFRAME)
    df = df.dropna().reset_index(drop=True)
    df = df[df['text'].str.strip() != ""]
    return df


# ---------- 🔧 Détection du tableau ----------------

def find_table_zone(df):
    """Repère l’en-tête du tableau et retourne lignes en dessous"""
    header = df[df['text'].str.contains("désignation|qté|quantité|prix|montant|tva", case=False, na=False)]
    if header.empty:
        return None, None

    y_header = header.iloc[0]['top']

    # Ligne d’entête
    header_line = df[(df['top'] >= y_header - 5) & (df['top'] <= y_header + 20)]

    # Corps du tableau
    rows = df[df['top'] > y_header + 20].copy()
    stop_idx = rows[rows['text'].str.contains("total|net à payer|base ht", case=False, na=False)].index.min()
    if not pd.isna(stop_idx):
        rows = rows.loc[:stop_idx-1]

    return header_line, rows


def group_rows(df, y_thresh=10):
    rows = []
    current_row = []
    last_y = None
    for _, word in df.sort_values("top").iterrows():
        if last_y is None or abs(word['top'] - last_y) <= y_thresh:
            current_row.append(word)
        else:
            rows.append(current_row)
            current_row = [word]
        last_y = word['top']
    if current_row:
        rows.append(current_row)
    return rows


def detect_columns(rows, x_thresh=40):
    x_positions = []
    for row in rows:
        for word in row:
            x_positions.append(word['left'])
    x_positions = sorted(list(set(x_positions)))

    columns = []
    for x in x_positions:
        if not columns or abs(x - columns[-1]) > x_thresh:
            columns.append(x)
    return columns


def align_table(rows, columns):
    table = []
    for row in rows:
        line = [""] * len(columns)
        for word in row:
            col_idx = min(range(len(columns)), key=lambda i: abs(columns[i] - word['left']))
            line[col_idx] += (" " + word['text']).strip()
        table.append([c.strip() for c in line])
    return table


# ---------- 🔧 Post-traitement ----------------

IGNORE_KEYWORDS = [
    "bon de livraison",
    "commande",
    "ventilation",
    "frais fixes",
    "merci de votre confiance"
]

def simplify_columns(columns, min_gap=80):
    simplified = []
    for x in sorted(columns):
        if not simplified or abs(x - simplified[-1]) > min_gap:
            simplified.append(x)
    return simplified


def is_product_row(row):
    """Vérifie si une ligne est un produit réel"""
    joined = " ".join(row).lower()

    # Ignorer les lignes parasites
    if any(k in joined for k in IGNORE_KEYWORDS):
        return False

    # Vérifie la présence d'au moins 2 nombres (quantité + prix/montant)
    nums = [c for c in row if re.search(r"\d", c)]
    if len(nums) < 2:
        return False

    return True


def normalize_headers(headers):
    """Nettoie et normalise les intitulés de colonnes OCR"""
    clean = []
    skip_next = False

    for i, h in enumerate(headers):
        if skip_next:
            skip_next = False
            continue

        h_low = h.lower().replace("|", "").strip()

        if h_low in ["réf", "réf.", "reference", "code"]:
            clean.append("Réf.")
        elif "désign" in h_low or "article" in h_low:
            clean.append("Désignation")
        elif "qté" in h_low or "quantité" in h_low:
            clean.append("Qté")
        elif "unit" in h_low and "prix" not in h_low:
            clean.append("Unité")
        elif "prix" in h_low and i + 1 < len(headers) and "unit" in headers[i+1].lower():
            clean.append("Prix Unitaire")
            skip_next = True
        elif "prix unitaire" in h_low:
            clean.append("Prix Unitaire")
        elif "montant" in h_low or "total" in h_low:
            clean.append("Montant")
        elif "tva" in h_low or "%" in h_low:
            clean.append("TVA")

    return clean


def map_rows_to_headers(table, headers):
    """Associe chaque ligne aux intitulés de colonnes"""
    mapped = []
    for row in table:
        if not is_product_row(row):
            continue
        line = {}
        for i, col in enumerate(headers):
            val = row[i] if i < len(row) else ""
            line[col] = val.strip()
        mapped.append(line)
    return mapped


# ---------- 🔧 OCR principal ----------------

def run_ocr(pdf_path):
    images = convert_from_path(pdf_path)
    pages_data = []

    for idx, img in enumerate(images, start=1):
        print(f"🔎 OCR page {idx}…")
        df = extract_words_with_positions(img)

        header_line, table_zone = find_table_zone(df)
        if header_line is None or table_zone is None or table_zone.empty:
            continue

        # On construit les colonnes à partir de l’entête
        rows = group_rows(table_zone)
        columns = simplify_columns(detect_columns(rows))
        header_row = group_rows(header_line)[0]
        headers_raw = [w['text'] for w in header_row]
        headers = normalize_headers(headers_raw)

        # Aligne et mappe
        table = align_table(rows, columns)
        products = map_rows_to_headers(table, headers)

        pages_data.append({
            "page": idx,
            "headers": headers,
            "products": products
        })

    return {"pages": pages_data}


# ---------- 🚀 Lancement ----------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Usage: python3 tesseract_runner.py <fichier.pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"🔎 OCR lancé sur : {pdf_path}")
    data = run_ocr(pdf_path)
    print("🎉 OCR terminé")
    print(json.dumps(data, indent=2, ensure_ascii=False))
