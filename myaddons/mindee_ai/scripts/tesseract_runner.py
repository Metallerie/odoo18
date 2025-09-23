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
        if not columns or abs(x - column
