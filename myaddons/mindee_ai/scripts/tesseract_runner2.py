#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os, json, re, unicodedata
from pdf2image import convert_from_path
import pytesseract

# ============== Utils texte ==============

def norm(s: str) -> str:
    if not s: return ""
    s = s.replace("\u2019", "'").replace("\u00A0", " ")
    return re.sub(r"\s+", " ", s).strip()

def fold(s: str) -> str:
    if not s: return ""
    s = norm(s)
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()

def to_float(s: str):
    if not s: return None
    s = s.replace("€","").replace("\u202f"," ").replace(" ", "")
    s = s.replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None

# ============== OCR ==============

def ocr_page_words(img):
    """Retourne les mots avec positions + le texte brut + les phrases."""
    text = pytesseract.image_to_string(img, lang="fra")
    phrases = [norm(l) for l in text.split("\n") if norm(l)]
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, lang="fra")
    words = []
    for i, t in enumerate(data["text"]):
        if str(t).strip():
            words.append({
                "text": norm(t),
                "left": int(data["left"][i]),
                "top": int(data["top"][i]),
                "width": int(data["width"][i]),
                "height": int(data["height"][i]),
            })
    return text, phrases, words, img.width, img.height

# ============== Détection zone tableau (coords) ==============

HEAD_RE = re.compile(r"ref|réf|designation|désignation|qt[eé]|quantit|prix|montant|tva", re.I)
FOOT_RE = re.compile(r"total|net\s*[àa]\s*payer|base\s*ht|total\s*t\.?v\.?a\.?", re.I)

def find_table_bbox(words, img_w, img_h):
    """Trouve y_top (entête) et y_bot (pied TOTAL/NET A PAYER)."""
    header_y = None
    footer_y = None

    # approx par lignes : groupe par top proche
    lines = {}
    for w in sorted(words, key=lambda x: x["top"]):
        y = w["top"]
        # snap Y dans des "bandes" de 8px
        band = y // 8
        lines.setdefault(band, []).append(w)

    # cherche entête
    for band in sorted(lines.keys()):
        line_txt = " ".join(w["text"] for w in sorted(lines[band], key=lambda x: x["left"]))
        if HEAD_RE.search(line_txt) and ("désign" in fold(line_txt) or "ref" in fold(line_txt) or "réf" in fold(line_txt)):
            header_y = min(w["top"] for w in lines[band])
            break

    # cherche pied (premier total sous l'entête)
    if header_y is not None:
        for band in sorted(lines.keys()):
            ly = min(w["top"] for w in lines[band])
            if ly <= header_y: 
                continue
            line_txt = " ".join(w["text"] for w in sorted(lines[band], key=lambda x: x["left"]))
            if FOOT_RE.search(line_txt):
                footer_y = ly
                break

    if header_y is None:
        # fallback : haut de page (mais on garde les produits via phrases)
        header_y = 0
    if footer_y is None:
        footer_y = img_h

    return {"x1": 0, "y1": int(header_y), "x2": int(img_w), "y2": int(footer_y)}

# ============== Parsing produits depuis les PHRASES ==============

IGNORE_LINE = re.compile(r"bon\s+de\s+livraison|commande|ventilation|frais\s+fixes", re.I)

UNITS = {"KG","PI","PCE","U","UN","M","ML","L","PAQ","MM"}

def default_vat_from_phrases(phrases):
    rates = re.findall(r"(\d{1,2}(?:[.,]\d)?)\s*%", " ".join(phrases))
    if not rates: 
        return None
    # garde le plus fréquent
    from collections import Counter
    r = Counter([r.replace(",", ".") for r in rates]).most_common(1)[0][0]
    return f"{r}%"

def is_number(tok):_
