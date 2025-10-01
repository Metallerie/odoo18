#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import json
import re
from pdf2image import convert_from_path
import pytesseract

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
    nums = []

    # Normaliser séparateurs
    for t in tokens:
        tok = t.replace(",", ".")
        if re.match(r"^\d+(\.\d+)?$", tok):
            nums.append(tok)

    result = {"raw": line, "type": "commentaire"}

    if len(nums) >= 3:
        # On prend les 3-4 derniers nombres comme qty, pu, total, (tva)
        qty = float(nums[-4]) if len(nums) >= 4 else float(nums[-3])
        price_unit = float(nums[-3]) if len(nums) >= 3 else None
        total = float(nums[-2]) if len(nums) >= 2 else None
        tva = float(nums[-1]) if len(nums) >= 1 else None

        # Désignation = tout avant les nombres de fin
        split_idx = max(line.rfind(nums[-3]), line.rfind(nums[-2]))
        designation = line[:split_idx].strip()

        result.update({
            "designation": designation,
            "qty": qty,
            "price_unit": price_unit,
            "total": total,
            "tva": tva,
            "type": "facture"
        })

        # Vérif cohérence
        if qty and price_unit and total:
            if abs(qty * price_unit - total) > 0.5:  # tolérance
                result["type"] = "facture_suspecte"
                result["reason"] = f"incohérence: {qty}*{price_unit} != {total}"
    else:
        result["reason"] = "moins de 3 nombres en fin de ligne"

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
            if parsed["type"] == "facture":
                print(f"✅ Facture → {parsed}")
            elif parsed["type"] == "facture_suspecte":
                print(f"⚠️ Facture suspecte → {parsed}")
            else:
                print(f"ℹ️ Commentaire → {parsed['raw']}")

            all_results.append(parsed)

    print("\n📊 Résultat final :")
    print(json.dumps(all_results, indent=2, ensure_ascii=False))
