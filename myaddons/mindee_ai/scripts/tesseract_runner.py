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
    """OCR avec coordonnées"""
    df = pytesseract.image_to_data(image, lang="fra", output_type=pytesseract.Output.DATAFRAME)
    df = df.dropna().reset_index(drop=True)
    df = df[df['text'].str.strip() != ""]
    return df


# ---------- 🔧 Détection du tableau ----------------

def find_table_zone(df):
    """Repère l’en-tête du tableau et retourne les lignes en dessous"""
    header = df[df['text'].str.contains("désignation|qté|quantité|prix|montant|tva", case=False, na=False)]
    if header.empty:
        return None

    y_header = header.iloc[0]['top']
    rows = df[df['top'] > y_header + 5].copy()

    # Stop quand on croise "TOTAL" ou "NET À PAYER"
    stop_idx = rows[rows['text'].str.contains("total|net à payer|base ht", case=False, na=False)].index.min()
    if not pd.isna(stop_idx):
        rows = rows.loc[:stop_idx-1]

    return rows


def group_rows(df, y_thresh=10):
    """Regroupe les mots en lignes selon Y"""
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
    """Détecte les colonnes en regroupant par X"""
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
    """Reconstruit le tableau en alignant texte sur colonnes"""
    table = []
    for row in rows:
        line = [""] * len(columns)
        for word in row:
            col_idx = min(range(len(columns)), key=lambda i: abs(columns[i] - word['left']))
            line[col_idx] += (" " + word['text']).strip()
        table.append([c.strip() for c in line])
    return table


# ---------- 🔧 Post-traitement ----------------

IGNORE_KEYWORDS = ["bon de livraison", "ventilation", "frais fixes"]

def simplify_columns(columns, min_gap=80):
    """Fusionne les colonnes trop proches"""
    simplified = []
    for x in sorted(columns):
        if not simplified or abs(x - simplified[-1]) > min_gap:
            simplified.append(x)
    return simplified


def is_product_row(row):
    """Vérifie si une ligne est un produit"""
    joined = " ".join(row).lower()
    if any(k in joined for k in IGNORE_KEYWORDS):
        return False
    # doit contenir au moins un chiffre
    return any(re.search(r"\d", c) for c in row)


def map_columns(table):
    """Mappe colonnes vers Ref / Desc / Qté / PU / Total / TVA"""
    mapped = []
    for row in table:
        if not is_product_row(row):
            continue

        # Remplissage par défaut
        line = {
            "ref": row[0].strip() if len(row) > 0 else "",
            "description": "",
            "quantity": "",
            "unit_price": "",
            "total_ht": "",
            "tva": ""
        }

        # Description = colonnes du milieu
        if len(row) > 2:
            line["description"] = " ".join(row[1:-4]).strip()

        # Les 4 dernières colonnes → quantités / PU / total / TVA
        if len(row) >= 4:
            line["quantity"]   = row[-4].strip()
            line["unit_price"] = row[-3].strip()
            line["total_ht"]   = row[-2].strip()
            line["tva"]        = row[-1].strip()

        mapped.append(line)
    return mapped


# ---------- 🔧 OCR principal ----------------

def run_ocr(pdf_path):
    images = convert_from_path(pdf_path)
    pages_data = []

    for idx, img in enumerate(images, start=1):
        print(f"🔎 OCR page {idx}…")
        df = extract_words_with_positions(img)

        table_zone = find_table_zone(df)
        if table_zone is None or table_zone.empty:
            continue

        rows = group_rows(table_zone)
        columns = simplify_columns(detect_columns(rows))
        table = align_table(rows, columns)
        products = map_columns(table)

        pages_data.append({
            "page": idx,
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
