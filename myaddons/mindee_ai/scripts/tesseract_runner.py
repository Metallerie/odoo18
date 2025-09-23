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
    # on nettoie un peu
    df['text'] = df['text'].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    return df

# ---------------- Trouver la zone tableau ----------------

def find_table_header_and_body(df):
    # repère l’entête par mots-clés
    head_hits = df[df['text'].str.contains(r"désign|qté|quantit|prix|montant|tva", case=False, na=False)]
    if head_hits.empty:
        return None, None
    y_head = head_hits.sort_values("top").iloc[0]['top']

    # bande d’entête
    header_band = df[(df['top'] >= y_head - 8) & (df['top'] <= y_head + 25)].copy()
    if header_band.empty:
        return None, None

    # corps sous l’entête
    body = df[df['top'] > y_head + 25].copy()

    # stop au premier bloc "TOTAL|NET A PAYER|BASE HT"
    stops = body[body['text'].str.contains(r"total|net\s*[àa]\s*payer|base\s*ht", case=False, na=False)]
    if not stops.empty:
        y_stop = stops.sort_values("top").iloc[0]['top']
        body = body[body['top'] < y_stop - 5]

    return header_band, body

# ---------------- Normalisation entête ----------------

def normalize_header_token(tok):
    t = tok.lower().replace("|", "").strip()
    t = re.sub(r"[^a-zàâçéèêëîïôûùüÿñ%\. ]", "", t)

    if t in {"réf", "réf.", "ref", "reference", "référence", "code"}:
        return "Réf."
    if "désign" in t or "article" in t or "produit" in t:
        return "Désignation"
    if "qté" in t or "quantit" in t:
        return "Qté"
    # Attention à Unité vs Unitaire (dans "Prix Unitaire")
    if "unit" in t and "prix" not in t:
        return "Unité"
    if "prix unitaire" in t:
        return "Prix Unitaire"
    if "prix" in t:
        return "Prix"
    if "unitaire" in t:
        return "Unitaire"
    if "montant" in t or "total" in t:
        return "Montant"
    if "tva" in t or "%" in t:
        return "TVA"
    return None

def build_header_columns(header_df, merge_gap=70):
    """
    Construit les colonnes à partir des mots de l’entête.
    Fusionne 'Prix' + 'Unitaire' -> 'Prix Unitaire' avec X moyen.
    Retourne liste ordonnée: [{'name': 'Réf.', 'x': 120}, ...]
    """
    tokens = header_df.sort_values("left").copy()
    cols = []
    i = 0
    used = set()
    while i < len(tokens):
        row = tokens.iloc[i]
        raw = row['text']
        name = normalize_header_token(raw)
        x_center = row['left'] + row['width'] / 2.0

        # sauter tokens non pertinents
        if not name:
            i += 1
            continue

        # fusion Prix + Unitaire
        if name in {"Prix", "Unitaire"}:
            # regarde le voisin immédiat
            j = i + 1
            merged = False
            while j < len(tokens) and (tokens.iloc[j]['left'] - row['left']) < 200:  # fenêtre raisonnable
                name2 = normalize_header_token(tokens.iloc[j]['text'])
                if {name, name2} == {"Prix", "Unitaire"}:
                    x2 = tokens.iloc[j]['left'] + tokens.iloc[j]['width'] / 2.0
                    x_center = (x_center + x2) / 2.0
                    name = "Prix Unitaire"
                    used.add(j)
                    merged = True
                    break
                j += 1
            if not merged and name in {"Prix", "Unitaire"}:
                # si on n'a que l’un des deux, on l’ignore (trop bruité)
                i += 1
                continue

        if name == "Montant":
            # éviter de dupliquer avec "Total"
            pass

        if i in used:
            i += 1
            continue

        cols.append({"name": name, "x": float(x_center)})
        i += 1

    # fusionner des entêtes dupliqués / proches
    cols = sorted(cols, key=lambda c: c["x"])
    merged = []
    for c in cols:
        if not merged:
            merged.append(c)
        else:
            if abs(c["x"] - merged[-1]["x"]) < merge_gap or c["name"] == merged[-1]["name"]:
                # si même colonne, garder le plus “lisible” en moyenne
                merged[-1]["x"] = (merged[-1]["x"] + c["x"]) / 2.0
                # garder le libellé le plus “riche” (ex: Prix Unitaire > Prix)
                if merged[-1]["name"] == "Prix" and c["name"] == "Prix Unitaire":
                    merged[-1]["name"] = "Prix Unitaire"
                if merged[-1]["name"] == "Unitaire" and c["name"] == "Prix Unitaire":
                    merged[-1]["name"] = "Prix Unitaire"
            else:
                merged.append(c)

    # garder uniquement l’ordre réel gauche→droite, et les colonnes utiles
    wanted = {"Réf.", "Désignation", "Qté", "Unité", "Prix Unitaire", "Montant", "TVA"}
    merged = [c for c in merged if c["name"] in wanted]
    # dédoublonner par nom (garde la 1ère qui apparait à gauche)
    seen = set()
    final = []
    for c in merged:
        if c["name"] not in seen:
            final.append(c)
            seen.add(c["name"])

    # trier gauche→droite
    final.sort(key=lambda c: c["x"])
    return final  # liste de dicts

# ---------------- Alignement lignes → colonnes ----------------

def build_bins_from_columns(cols):
    """
    Construit des bandes (min_x, max_x, name) à partir des centres X des colonnes.
    """
    if not cols:
        return []
    cols = sorted(cols, key=lambda c: c["x"])
    bins = []
    for idx, c in enumerate(cols):
        if idx == 0:
            left = 0
        else:
            left = (cols[idx-1]["x"] + c["x"]) / 2.0
        if idx == len(cols) - 1:
            right = 1e9
        else:
            right = (c["x"] + cols[idx+1]["x"]) / 2.0
        bins.append({"name": c["name"], "left": left, "right": right})
    return bins

def group_words_by_rows(df, y_thresh=10):
    rows = []
    cur = []
    last_y = None
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

def assign_words_to_columns(row_words, bins):
    """
    Retourne un dict {col_name: "texte"} pour une ligne donnée.
    """
    out = {b["name"]: "" for b in bins}
    for _, w in pd.DataFrame(row_words).sort_values("left").iterrows():
        x = w['left'] + w['width'] / 2.0
        for b in bins:
            if b["left"] <= x <= b["right"]:
                out[b["name"]] = (out[b["name"]] + " " + w['text']).strip()
                break
    return out

# ---------------- Filtrage lignes produits ----------------

IGNORE_LINE_PATTERNS = [
    r"bon\s+de\s+livraison",
    r"commande",
    r"ventilation",
    r"frais\s+fixes",
    r"merci\s+de\s+votre\s+confiance",
]

def looks_like_product(cells):
    joined = " ".join(cells.values()).lower()
    if any(re.search(p, joined) for p in IGNORE_LINE_PATTERNS):
        return False

    # au moins un nombre dans Montant ou Prix Unitaire
    has_price = any(re.search(r"\d", cells.get(k, "")) for k in ["Montant", "Prix Unitaire"])
    # une désignation lisible
    has_desc = len(cells.get("Désignation", "").strip()) >= 2
    # une ref plausible (alphanum avec chiffre)
    ref = cells.get("Réf.", "")
    has_ref = bool(re.search(r"[0-9]", ref)) and bool(re.search(r"[A-Za-z0-9\-]+", ref))

    return (has_desc and (has_price or has_ref))

# ---------------- OCR principal ----------------

def run_ocr(pdf_path):
    images = convert_from_path(pdf_path)
    pages = []

    for p, img in enumerate(images, start=1):
        print(f"🔎 OCR page {p}…")
        df = ocr_df(img)
        header_df, body_df = find_table_header_and_body(df)
        if header_df is None or body_df is None or body_df.empty:
            continue

        # colonnes depuis l’entête
        header_cols = build_header_columns(header_df)
        if not header_cols:
            continue
        bins = build_bins_from_columns(header_cols)

        # regrouper en lignes puis remplir cellules par colonne
        rows = group_words_by_rows(body_df, y_thresh=10)
        products = []
        for rw in rows:
            cells = assign_words_to_columns(rw, bins)

            # petit nettoyage typique sur Qté/Unité
            # si "Qté" contient "KG|PI|M|U" à la fin -> pousser dans Unité
            if "Qté" in cells and "Unité" in cells:
                m = re.match(r"^([0-9]+[.,]?[0-9]*)\s*([A-Za-z]+)$", cells["Qté"])
                if m and not cells["Unité"]:
                    cells["Qté"] = m.group(1)
                    cells["Unité"] = m.group(2)

            if looks_like_product(cells):
                products.append(cells)

        pages.append({
            "page": p,
            "headers": [c["name"] for c in header_cols],
            "products": products,
        })

    return {"pages": pages}

# ---------------- CLI ----------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Usage: python3 tesseract_runner.py <fichier.pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"🔎 OCR lancé sur : {pdf_path}")
    data = run_ocr(pdf_path)
    print("🎉 OCR terminé")
    print(json.dumps(data, indent=2, ensure_ascii=False))
