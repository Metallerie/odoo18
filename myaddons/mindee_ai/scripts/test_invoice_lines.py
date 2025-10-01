#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import re
import json
from pdf2image import convert_from_path
import pytesseract

# ---------------- Utils ----------------
def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\u2019", "'").replace("\u00A0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def safe_float(s):
    try:
        return float(str(s).replace(",", "."))
    except:
        return None

# ---------------- Extraction ----------------
EXCLUDE_KEYWORDS = [
    "siren", "rcs", "iban", "bic", "capital", "intracom",
    "total", "net", "ht", "tva", "eco-part", "merci",
    "facture", "bon de livraison", "base", "ventilation",
    "attention", "comptoir", "au capital", "sas",
]

def parse_line(line):
    raw = normalize_text(line)
    tokens = raw.split()

    # Vérif exclu mots-clés
    for kw in EXCLUDE_KEYWORDS:
        if kw in raw.lower():
            return {"raw": raw, "type": "commentaire", "reason": f"mot-clé {kw}"}

    # Vérif au moins 4 tokens (Ref + désignation + 3 nombres)
    if len(tokens) < 4:
        return {"raw": raw, "type": "commentaire", "reason": "trop court"}

    # Réf candidate (doit être alpha-numérique sans espace)
    ref = tokens[0]
    if not re.match(r"^[A-Z0-9\-]+$", ref, re.IGNORECASE):
        return {"raw": raw, "type": "commentaire", "reason": "pas de ref valide"}

    # Extraire les nombres en fin de ligne
    nums = [safe_float(t) for t in tokens if re.match(r"^[0-9]+([.,][0-9]+)?$", t)]
    if len(nums) < 3:
        return {"raw": raw, "type": "commentaire", "reason": "moins de 3 nombres"}

    qty, pu, total, *rest = nums[-3:]  # on prend les 3 derniers
    tva = rest[0] if rest else None

    # Vérif cohérence simple
    if qty and pu and total:
        expected = round(qty * pu, 2)
        if abs(expected - total) > 1.0:  # tolérance 1€
            return {
                "raw": raw,
                "type": "commentaire",
                "reason": f"incohérence: {qty}*{pu} != {total}"
            }

    designation = " ".join(tokens[1:-3]) if len(tokens) > 4 else ""

    return {
        "raw": raw,
        "type": "facture",
        "ref": ref,
        "designation": designation,
        "qty": qty,
        "price_unit": pu,
        "total": total,
        "tva": tva,
    }

# ---------------- OCR ----------------
def run_ocr(pdf_path):
    results = []
    images = convert_from_path(pdf_path)
    print(f"⚡ OCR lancé sur : {pdf_path}\n")
    for idx, img in enumerate(images, start=1):
        text = pytesseract.image_to_string(img, lang="fra")
        lines = [normalize_text(p) for p in text.split("\n") if normalize_text(p)]
        print(f"📄 --- Analyse page {idx} ---")
        for line in lines:
            parsed = parse_line(line)
            if parsed["type"] == "facture":
                print(f"✅ Facture → {parsed}")
            else:
                print(f"ℹ️ Commentaire → {parsed['raw']}")
            results.append(parsed)
    return results

# ---------------- CLI ----------------
def main():
    if len(sys.argv) < 2:
        print("Usage: python test_invoice_lines.py <pdf_file>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    if not os.path.exists(pdf_file):
        print(json.dumps({"error": f"File not found: {pdf_file}"}))
        sys.exit(1)

    results = run_ocr(pdf_file)
    print("\n📊 Résultat final :")
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
