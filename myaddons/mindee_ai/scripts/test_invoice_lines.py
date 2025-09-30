# -*- coding: utf-8 -*-
import json
import re
import sys
import subprocess
from pathlib import Path

# ⚙️ Config chemins
VENV_PYTHON = "/data/odoo/odoo18-venv/bin/python3"
TESSERACT_SCRIPT = "/data/odoo/metal-odoo18-p8179/myaddons/mindee_ai/scripts/tesseract_runner.py"

def run_ocr(pdf_path: Path):
    """Lance tesseract_runner.py sur un PDF et retourne le JSON"""
    print(f"⚡ OCR lancé sur : {pdf_path}")
    result = subprocess.run(
        [VENV_PYTHON, TESSERACT_SCRIPT, str(pdf_path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=180, encoding="utf-8"
    )
    if result.returncode != 0:
        print("❌ Erreur OCR:", result.stderr)
        sys.exit(1)
    return json.loads(result.stdout.strip())

# ---------------- Extraction des lignes de tableau ----------------

def extract_table_lines(phrases):
    """Récupère uniquement les lignes du tableau (entre en-tête et TOTAL)."""
    lines = []
    in_table = False
    buffer = ""

    for ph in phrases:
        if "Réf. Désignation" in ph:  # début tableau
            in_table = True
            continue
        if in_table and (ph.startswith("Ventilation") or ph.startswith("TOTAL")):
            break

        if in_table:
            buffer += " " + ph.strip()
            nums = re.findall(r"\d+[,.]?\d*", buffer)

            # On valide une ligne quand on a au moins 4 nombres (Qté, PU, Montant, TVA)
            if len(nums) >= 4:
                lines.append(buffer.strip())
                buffer = ""

    return lines

def parse_table_line(line):
    """Découpe une ligne en colonnes (Réf, Désignation, Qté, PU, Montant, TVA)."""
    parts = line.split()
    ref = parts[0]

    # Récupère les 4 derniers nombres (Qté, PU, Montant, TVA)
    nums = re.findall(r"\d+[,.]?\d*", line)
    if len(nums) < 4:
        return None

    qty = nums[-4]
    pu = nums[-3]
    montant = nums[-2]
    tva = nums[-1]

    # Désignation = tout entre réf et le premier nombre trouvé
    desig_zone = line.replace(ref, "", 1)
    for n in [qty, pu, montant, tva]:
        desig_zone = desig_zone.replace(n, "")
    designation = desig_zone.strip()

    return {
        "ref": ref,
        "designation": designation,
        "qty": qty.replace(",", "."),
        "price_unit": pu.replace(",", "."),
        "total": montant.replace(",", "."),
        "tva": tva,
    }

# ---------------- Main ----------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_invoice_lines.py <facture.pdf>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"❌ Fichier introuvable : {pdf_path}")
        sys.exit(1)

    ocr_data = run_ocr(pdf_path)

    all_lines = []
    for page in ocr_data.get("pages", []):
        table_lines = extract_table_lines(page.get("phrases", []))
        for l in table_lines:
            parsed = parse_table_line(l)
            if parsed:
                all_lines.append(parsed)

    print("\n✅ Lignes de facture extraites :")
    print(json.dumps(all_lines, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
