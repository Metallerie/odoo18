# -*- coding: utf-8 -*-
import json
import re
import sys
from pathlib import Path
from pprint import pprint

def load_ocr_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_invoice_lines(ocr_data):
    """Essaie d’extraire les lignes de facture depuis OCR JSON ou raw_text"""
    lines = []

    # 1️⃣ Si déjà présent dans le JSON (cas Mindee)
    for page in ocr_data.get("pages", []):
        if "line_items" in page:
            for item in page["line_items"]:
                line = {
                    "product": item.get("description") or item.get("label"),
                    "qty": float(item.get("quantity") or 1),
                    "price_unit": float(item.get("unit_price") or 0),
                    "tax": float(item.get("tax_amount") or 0),
                    "subtotal": float(item.get("total") or 0),
                }
                lines.append(line)

    # 2️⃣ Sinon → parser dans le raw_text
    if not lines:
        phrases = []
        for page in ocr_data.get("pages", []):
            phrases.extend(page.get("phrases", []))
        text = " ".join(phrases)

        # Regex simple : "Désignation Qté PU Total TVA"
        regex = re.compile(
            r"(?P<product>[A-Za-z0-9\s\-]+)\s+"
            r"(?P<qty>\d+[,.]?\d*)\s+"
            r"(?P<pu>\d+[,.]?\d*)\s+"
            r"(?P<total>\d+[,.]?\d*)",
            re.MULTILINE,
        )
        for m in regex.finditer(text):
            qty = float(m.group("qty").replace(",", "."))
            pu = float(m.group("pu").replace(",", "."))
            total = float(m.group("total").replace(",", "."))
            lines.append({
                "product": m.group("product").strip(),
                "qty": qty,
                "price_unit": pu,
                "subtotal": total,
                "tax": 0.0,  # à améliorer
            })

    return lines

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_invoice_lines.py <ocr_json_file>")
        sys.exit(1)

    path = Path(sys.argv[1])
    ocr_data = load_ocr_json(path)

    invoice_lines = parse_invoice_lines(ocr_data)

    print("✅ Lignes extraites :")
    pprint(invoice_lines)

if __name__ == "__main__":
    main()
