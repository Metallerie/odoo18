#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, json, re
from pdf2image import convert_from_path
import pytesseract
import pandas as pd

# ---------------- utils ----------------

UNIT_TOKENS = {"KG","PI","PCE","U","UN","M","ML","L","PAQ","PAQUET","MM"}
IGNORE_LINES = [
    r"bon\s+de\s+livraison", r"commande", r"ventilation", r"frais\s+fixes",
    r"merci\s+de\s+votre\s+confiance", r"net\s*[àa]\s*payer", r"base\s*ht", r"total"
]

def ocr_df(image):
    df = pytesseract.image_to_data(image, lang="fra", output_type=pytesseract.Output.DATAFRAME)
    df = df.dropna().reset_index(drop=True)
    df = df[(df['text'].astype(str).str.strip() != "") & (df['conf'] != -1)]
    df['text'] = df['text'].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    return df

def to_float(s):
    if not s: return None
    s = s.replace("€","").replace("\u202f"," ").replace(" ", "")
    s = s.replace(",", ".")
    m = re.search(r"-?\d+(\.\d+)?", s)
    return float(m.group(0)) if m else None

def has_number(s): return bool(re.search(r"\d", s or ""))

def split_qty_unit(tok):
    if not tok: return None, None
    t = tok.replace(",", ".")
    # "96.58 KG" -> qty=96.58, unit=KG
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]+)$", t)
    if m: return to_float(m.group(1)), m.group(2).upper()
    # "KG96.58" -> qty=96.58, unit=KG
    m = re.match(r"^([A-Za-z]+)\s*([0-9]+(?:\.[0-9]+)?)$", t)
    if m: return to_float(m.group(2)), m.group(1).upper()
    # "1PI"
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]{1,3})$", t)
    if m: return to_float(m.group(1)), m.group(2).upper()
    # "1" seul
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", t): return to_float(t), None
    return None, None

def looks_ref(tok):
    if not tok: return False
    t = tok.replace("-", "")
    return bool(re.fullmatch(r"[A-Z0-9]{4,}", t))  # ex: 70823, 011110010, ABCD12

def find_default_vat(page_text):
    rates = re.findall(r"(\d{1,2}(?:[.,]\d)?)\s*%", page_text)
    if not rates: return None
    # prend le plus fréquent
    from collections import Counter
    r = Counter([x.replace(",", ".") for x in rates]).most_common(1)[0][0]
    return f"{r}%"

def row_text(words):
    return " ".join(w['text'] for _, w in pd.DataFrame(words).sort_values("left").iterrows())

def is_ignored_line(txt):
    low = txt.lower()
    return any(re.search(p, low) for p in IGNORE_LINES)

# ---------------- regroupement lignes ----------------

def group_words_by_rows(df, y_thresh=10):
    rows, cur, last_y = [], [], None
    for _, w in df.sort_values("top").iterrows():
        y = w['top']
        if last_y is None or abs(y - last_y) <= y_thresh:
            cur.append(w)
        else:
            rows.append(cur); cur = [w]
        last_y = y
    if cur: rows.append(cur)
    return rows

# ---------------- parsing d'une ligne ----------------

def parse_product_row(words, default_vat=None):
    # trie gauche -> droite
    ws = list(pd.DataFrame(words).sort_values("left").to_dict("records"))
    txt = " ".join(w["text"] for w in ws)

    if is_ignored_line(txt): 
        return None

    # sépare tokens texte / nombres avec coordonnées
    tokens = [{"t":w["text"], "x": w["left"] + w["width"]/2.0} for w in ws]

    # détecte nombres (avec virgule/point)
    num_idx = [i for i,tk in enumerate(tokens) if has_number(tk["t"])]
    if len(num_idx) == 0:
        return None

    # Montant = nombre le plus à droite
    rightmost = max(num_idx, key=lambda i: tokens[i]["x"])
    montant = to_float(tokens[rightmost]["t"])

    # PU = nombre à gauche du montant (le plus proche)
    pu = None
    left_nums = [i for i in num_idx if tokens[i]["x"] < tokens[rightmost]["x"]]
    if left_nums:
        pu = to_float(tokens[max(left_nums, key=lambda i: tokens[i]["x"])]["t"])

    # Qté / Unité : cherche à gauche de PU sinon à gauche du Montant
    q_idx_zone_x = tokens[rightmost]["x"]
    if left_nums:
        q_idx_zone_x = tokens[max(left_nums, key=lambda i: tokens[i]["x"])]["x"]
    qty, unit = None, None
    left_candidates = [i for i,tk in enumerate(tokens) if tokens[i]["x"] < q_idx_zone_x]
    # essaie patterns collés (KG96.58, 1PI) puis couple nombre + unit séparés
    for i in reversed(left_candidates):
        q, u = split_qty_unit(tokens[i]["t"])
        if q is not None:
            qty, unit = q, u
            break
    if qty is None:
        # cherche nombre puis token unité juste après
        for i in reversed(left_candidates):
            if re.fullmatch(r"[0-9]+(?:[.,][0-9]+)?", tokens[i]["t"].replace(",", ".")):
                q = to_float(tokens[i]["t"])
                # token suivant (à droite) proche = unité ?
                nxt = None
                for j in range(i+1, len(tokens)):
                    if tokens[j]["x"] > tokens[i]["x"]:
                        nxt = tokens[j]; break
                if q is not None and nxt and nxt["t"].upper() in UNIT_TOKENS:
                    qty, unit = q, nxt["t"].upper()
                    break
                if q is not None and unit is None:
                    qty = q
                    break

    # Ref = premier token à gauche qui ressemble à un code
    ref = ""
    for tk in tokens:
        if looks_ref(tk["t"]):
            ref = tk["t"]
            break

    # TVA : cherche un % dans la ligne, sinon code court (10/20) sinon défaut
    tva = ""
    m = re.search(r"(\d{1,2}(?:[.,]\d)?)\s*%", txt)
    if m:
        tva = f"{m.group(1).replace(',', '.')}%"
    elif default_vat:
        tva = default_vat

    # Désignation = tout le texte entre ref et les colonnes numériques
    # on coupe avant le premier nombre significatif
    first_num_x = min(tokens[i]["x"] for i in num_idx)
    desc_tokens = []
    started_after_ref = False if ref else True
    for tk in tokens:
        if not started_after_ref:
            if tk["t"] == ref:
                started_after_ref = True
            continue
        if tk["x"] >= first_num_x:  # on stoppe avant le bloc chiffres
            break
        # on garde du texte non numérique
        if not has_number(tk["t"]) or re.search(r"[A-Za-z]", tk["t"]):
            # évite d’empiler l’unité si on l’a déjà sortie
            if unit and tk["t"].upper() == unit:
                continue
            desc_tokens.append(tk["t"])
    description = " ".join(desc_tokens).strip()

    # garde uniquement les lignes qui ont soit un montant, soit une désignation + ref
    if montant is None and not (ref and description):
        return None

    out = {
        "Réf.": ref,
        "Désignation": description,
        "Qté": f"{qty}".replace("None","") if qty is not None else "",
        "Unité": unit or "",
        "Prix Unitaire": f"{pu}".replace("None","") if pu is not None else "",
        "Montant": f"{montant}".replace("None","") if montant is not None else "",
        "TVA": tva
    }

    # nettoyage jolis formats (virgules FR)
    for k in ["Qté","Prix Unitaire","Montant"]:
        if out[k]:
            try:
                v = float(out[k])
                out[k] = f"{v:.2f}".replace(".", ",")
            except:
                pass

    return out

# ---------------- moteur ----------------

def run_ocr(pdf_path):
    images = convert_from_path(pdf_path)
    pages = []

    for p, img in enumerate(images, start=1):
        print(f"🔎 OCR page {p}…")
        df = ocr_df(img)
        page_text = " ".join(df['text'].tolist())
        default_vat = find_default_vat(page_text)

        rows = group_words_by_rows(df, y_thresh=10)
        products = []
        for words in rows:
            parsed = parse_product_row(words, default_vat=default_vat)
            if parsed:
                # filtre brut: éviter d’avaler les lignes de totaux
                if is_ignored_line(" ".join(w['text'] for w in words)):
                    continue
                products.append(parsed)

        if products:
            pages.append({
                "page": p,
                "headers": ["Réf.","Désignation","Qté","Unité","Prix Unitaire","Montant","TVA"],
                "products": products
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
