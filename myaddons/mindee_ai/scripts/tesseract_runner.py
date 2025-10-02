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
