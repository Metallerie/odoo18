# -*- coding: utf-8 -*-
import json
import re
import sys
import subprocess
from pathlib import Path
from pprint import pprint

# ⚙️ Config chemins
VENV_PYTHON = "/data/odoo/odoo18-venv/bin/python3"
TESSERACT_SCRIPT = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/scripts/tesseract_runner.py"

def run_ocr(pdf_path: Path):
    """Lance tesseract_runner.py sur un PDF et retourne le JSON"""
    result = subprocess.run(
        [VENV_PYTHON, TESSERACT_SCRIPT, str(pdf_path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=180, encoding="utf-8"
    )
    if result.returncode != 0:
        print("❌ Erreur OCR:", result.stderr)
        sys.exit(1)
    return json.loads(result.stdout.strip())

def parse_invoice_lines(ocr_data):
    """Extrait les lignes de facture depuis OCR JSON"""
    lines = []

    # 🔎 Récupère tout le texte brut OCR
    phrases = []
    for page in ocr_data.get("pages", []):
        phrases.extend(page.get("phrases", []))
    text = " ".join(phrases)

    # 📝 Regex adaptée aux factures type CCL (Qté | PU | Montant)
    regex = re.compile(
        r"(?P<product>[A-Za-z0-9\s\-\.,]+?)\s+"
        r"(?P<qty>\d+[,.]?\d*)\s+"
        r"(?P<pu>\d+[,.]?\d*)\s+"
        r"(?P<total>\d+[,.]?\d*)",
        re.MULTILINE,
    )

    for m in regex.finditer(text):
        qty = float(m.group("qty").replace(",", "."))
        pu = float(m.group("pu").replace(",", "."))
        total = float(m.group("total").replace(",", "."))
        product = m.group("product").strip()

        # ⚖️ Vérifie cohérence PU * Qté ≈ Total
        if abs((qty * pu) - total) < 0.05:
            lines.append({
                "product": product,
                "qty": qty,
                "price_unit": pu,
                "subtotal": total,
                "tax": 0.0,  # à améliorer
            })

    return lines

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_invoice_lines.py <facture.pdf>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"❌ Fichier introuvable : {pdf_path}")
        sys.exit(1)

    # 1️⃣ OCR
    ocr_data = run_ocr(pdf_path)

    # 2️⃣ Parsing des lignes
    invoice_lines = parse_invoice_lines(ocr_data)

    # 3️⃣ Résultat
    print("\n✅ Lignes extraites :")
    pprint(invoice_lines)

if __name__ == "__main__":
    main()
