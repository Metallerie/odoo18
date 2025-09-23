#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import re
from pdf2image import convert_from_path
import pytesseract
import pandas as pd


# ---------- 🔧 Extraction OCR avec coordonnées ----------------

def extract_words_with_positions(image):
    """Renvoie un DataFrame avec texte + coordonnées"""
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

    # Position Y de l’en-tête
    y_header = header.iloc[0]['top']

    # On prend tout ce qui est sous l’en-tête
    rows = df[df['top'] > y_header + 5].copy()

    # Stop quand on croise "TOTAL"
    stop_idx = rows[rows['text'].str.contains("total|net à payer|base ht", case=False, na=False)].index.min()
    if not pd.isna(stop_idx):
        rows = rows.loc[:stop_idx-1]

    return rows


def group_rows(df, y_thresh=10):
    """Regroupe les mots en lignes selon leur coordonnée Y"""
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
    """Détecte les colonnes à partir des coordonnées X"""
    x_positions = []
    for row in rows:
        for word in row:
            x_positions.append(word['left'])
    x_positions = sorted(list(set(x_positions)))

    # Regroupe les colonnes proches
    columns = []
    for x in x_positions:
        if not columns or abs(x - columns[-1]) > x_thresh:
            columns.append(x)
    return columns


def align_table(rows, columns):
    """Reconstruit le tableau en alignant texte sur les colonnes"""
    table = []
    for row in rows:
        line = [""] * len(columns)
        for word in row:
            # Trouver la colonne la plus proche
            col_idx = min(range(len(columns)), key=lambda i: abs(columns[i] - word['left']))
            line[col_idx] += (" " + word['text']).strip()
        table.append(line)
    return table


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
        columns = detect_columns(rows)
        table = align_table(rows, columns)

        pages_data.append({
            "page": idx,
            "table": {
                "columns": columns,
                "rows": table
            }
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
