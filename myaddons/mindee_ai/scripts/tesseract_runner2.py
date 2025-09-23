#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, json, re
from pdf2image import convert_from_path
import pytesseract
import pandas as pd

# ---------------- OCR utils ----------------

def ocr_df(image):
    df = pytesseract.image_to_data(image, lang="fra", output_type=pytesseract.Output.DATAFRAME)
    df = df.dropna().reset_index(drop=True)
    df = df[df['text'].astype(str).str.strip() != ""]
    return df

# ---------------- Zone du tableau ----------------

def find_table_zone(df):
    """Trouve les limites verticales (Y) du tableau entre l'entête et TOTAL"""
    header = df[df['text'].str.contains("désign|qté|quantité|prix|montant|tva", case=False, na=False)]
    if header.empty:
        return None

    y_header = header['top'].min()

    footer = df[df['text'].str.contains("total|net à payer|base ht", case=False, na=False)]
    if not footer.empty:
        y_footer = footer['top'].min()
    else:
        y_footer = df['top'].max()

    return y_header, y_footer

def extract_table_words(df):
    """Filtre les mots situés dans la zone tableau"""
    zone = find_table_zone(df)
    if not zone:
        return pd.DataFrame()
    y_top, y_bottom = zone
    return df[(df['top'] > y_top) & (df['top'] < y_bottom)]

# ---------------- Groupement lignes ----------------

def group_rows(df, y_thresh=10):
    rows, cur, last_y = [], [], None
    for _, w in df.sort_values("top").iterrows():
        y = w['top']
        if last_y is None or abs(y - last_y) <= y_thresh:
            cur.append(w)
        else:
            rows.append(cur)
            cur = [w]
        last_y = y
    if cur:
        rows.append(cur)
    return rows

# ---------------- Normalisation entête ----------------

def normalize_headers(words):
    """Transforme les mots de l’entête en colonnes standardisées"""
    headers = []
    text_line = " ".join([w['text'] for w in words]).lower()

    if "réf" in text_line or "ref" in text_line:
        headers.append("Réf.")
    headers.append("Désignation")
    if "qté" in text_line or "quantité" in text_line:
        headers.append("Qté")
    if "unité" in text_line:
        headers.append("Unité")
    headers.append("Prix Unitaire")
    headers.append("Montant")
    if "tva" in text_line:
        headers.append("TVA")

    return headers

# ---------------- Alignement ligne -> colonnes ----------------

def map_row_to_headers(words, headers):
    """Distribue les mots d'une ligne en colonnes simples"""
    line_txt = " ".join(w['text'] for w in words)

    # Ref = premier token numérique/alphanum
    ref = ""
    tokens = line_txt.split()
    if tokens and re.match(r"^[A-Za-z0-9]+$", tokens[0]):
        ref = tokens[0]

    # Montant = dernier nombre
    nums = re.findall(r"\d+[.,]?\d*", line_txt)
    montant = nums[-1] if nums else ""

    # PU = avant dernier nombre si dispo
    pu = nums[-2] if len(nums) >= 2 else ""

    # Qté = premier nombre si dispo
    qte = nums[0] if nums else ""

    # Description = texte entre Ref et chiffres
    desc_tokens = []
    for tok in tokens[1:]:
        if re.search(r"\d", tok):
            break
        desc_tokens.append(tok)
    description = " ".join(desc_tokens)

    row = {}
    for h in headers:
        if h == "Réf.":
            row[h] = ref
        elif h == "Désignation":
            row[h] = description
        elif h == "Qté":
            row[h] = qte
        elif h == "Prix Unitaire":
            row[h] = pu
        elif h == "Montant":
            row[h] = montant
        elif h == "Unité":
            # essaie de détecter unité dans la ligne
            u = re.findall(r"[A-Za-z]{2,3}", line_txt)
            row[h] = u[-1] if u else ""
        elif h == "TVA":
            m = re.search(r"(\d{1,2})\s*%", line_txt)
            row[h] = m.group(1) + "%" if m else ""
    return row

# ---------------- OCR principal ----------------

def run_ocr(pdf_path):
    images = convert_from_path(pdf_path)
    pages = []

    for p, img in enumerate(images, start=1):
        print(f"🔎 OCR page {p}…")
        df = ocr_df(img)
        table_df = extract_table_words(df)
        if table_df.empty:
            continue

        rows = group_rows(table_df, y_thresh=12)

        # première ligne = entête
        headers = normalize_headers(rows[0])

        products = []
        for words in rows[1:]:
            mapped = map_row_to_headers(words, headers)
            if any(mapped.values()):
                products.append(mapped)

        pages.append({
            "page": p,
            "headers": headers,
            "products": products
        })

    return {"pages": pages}

# ---------------- CLI ----------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Usage: python3 tesseract_runner2.py <fichier.pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"🔎 OCR lancé sur : {pdf_path}")
    data = run_ocr(pdf_path)
    print("🎉 OCR terminé")
    print(json.dumps(data, indent=2, ensure_ascii=False))
