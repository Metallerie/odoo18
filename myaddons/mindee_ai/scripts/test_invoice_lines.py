#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import json
import re
from pdf2image import convert_from_path
import pytesseract

# ---------------- Config ----------------
# Liste des unités connues (tu peux enrichir)
KNOWN_UNITS = {
    "m", "ml", "ml-o", "mm", "cm", "km",
    "m2", "m³", "m3", "ft", "ft²", "ft³", "yd", "in", "in³",
    "kg", "kg-o", "g", "lb", "oz", "t",
    "l", "litre", "ml", "cl", "dl", "gal", "qt",
    "pi", "u", "unité", "unités", "douzaines",
    "jours", "heures"
}

# ---------------- OCR ----------------
def run_ocr(pdf_path):
    pages_data = []
    images = convert_from_path(pdf_path)

    for idx, img in enumerate(images, start=1):
        text = pytesseract.image_to_string(img, lang="fra")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        pages_data.append((idx, lines))
    return pages_data

# ---------------- Parsing ----------------
def parse_invoice_line(line):
    tokens = line.split()
    if not tokens:
        return None

    result = {"raw": line}

    # Ref = premier token alphanumérique long
    ref = None
    if re.match(r"^[A-Za-z0-9]{4,}$", tokens[0]):
        ref = tokens[0]
        tokens = tokens[1:]

    result["ref"] = ref
    qty = price_unit = total = tva = None
    designation_parts = []
    unit = None

    for tok in tokens:
        clean_tok = tok.replace(",", ".")
        if re.match(r"^\d+(\.\d+)?$", clean_tok):
            val = float(clean_tok)
            if qty is None:
                qty = val
            elif price_unit is None:
                price_unit = val
            elif total is None:
                total = val
            elif tva is None:
                tva = val
        elif tok.lower() in KNOWN_UNITS:
            unit = tok
        else:
            designation_parts.append(tok)

    designation = " ".join(designation_parts)

    result.update({
        "designation": designation.strip(),
        "qty": qty,
        "unit": unit,
        "price_unit": price_unit,
        "total": total,
        "tva": tva
    })

    # Vérification cohérence
    if qty is not None and price_unit is not None and total is not None:
        if abs(qty * price_unit - total) < 0.5:  # tolérance
            result["type"] = "facture"
        else:
            result["type"] = "commentaire"
            result["reason"] = f"incohérence: {qty}*{price_unit} != {total}"
    else:
        result["type"] = "commentaire"
        result["reason"] = "données incomplètes"

    return result

# ---------------- CLI ----------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_invoice_lines.py <pdf_file>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    if not os.path.exists(pdf_file):
        print(json.dumps({"error": f"File not found: {pdf_file}"}))
        sys.exit(1)

    print(f"⚡ OCR lancé sur : {pdf_file}\n")
    pages = run_ocr(pdf_file)

    all_results = []
    for page_idx, lines in pages:
        print(f"📄 --- Analyse page {page_idx} ---")
        for line in lines:
            parsed = parse_invoice_line(line)
            if not parsed:
                continue

            if parsed["type"] == "facture":
                print(f"✅ Facture → Ref={parsed.get('ref')} | Désignation={parsed.get('designation')} "
                      f"| Qté={parsed.get('qty')} {parsed.get('unit') or ''} | PU={parsed.get('price_unit')} "
                      f"| Total={parsed.get('total')} | TVA={parsed.get('tva')}")
            else:
                reason = parsed.get("reason", "autre")
                print(f"ℹ️ Commentaire ({reason}) → {parsed['raw']}")

            all_results.append(parsed)

    print("\n📊 Résultat final (factures + commentaires) :")
    print(json.dumps(all_results, indent=2, ensure_ascii=False))
