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

            # On valide une ligne quand on a au moins 3 nombres (Qté, PU, Total)
            if len(nums) >= 3:
                lines.append(buffer.strip())
                buffer = ""

    return lines

def parse_table_line(line, debug=False):
    """Découpe une ligne en colonnes (Réf, Désignation, Qté, PU, Montant)."""
    parts = line.split()
    ref = parts[0]

    # 1️⃣ Vérifie que le "ref" ressemble à un code article
    if not re.match(r"^[A-Za-z0-9\-]+$", ref):
        if debug:
            print(f"⚠️ Ignorée (pas de réf valide) → {line}")
        return None

    # 2️⃣ Récupère les nombres
    nums = re.findall(r"\d+[,.]?\d*", line)
    if len(nums) < 3:
        if debug:
            print(f"⚠️ Ignorée (pas assez de nombres) → {line}")
        return None

    qty, pu, montant = nums[-3], nums[-2], nums[-1]

    # 3️⃣ Convertit en float
    try:
        qty_f = float(qty.replace(",", "."))
        pu_f = float(pu.replace(",", "."))
        montant_f = float(montant.replace(",", "."))
    except ValueError:
        if debug:
            print(f"⚠️ Ignorée (conversion impossible) → {line}")
        return None

    # 4️⃣ Vérifie cohérence PU * Qté ≈ Montant
    if not (abs((qty_f * pu_f) - montant_f) < max(0.05, 0.01 * montant_f)):
        if debug:
            print(f"⚠️ Ignorée (incohérence: {qty_f}*{pu_f} != {montant_f}) → {line}")
        return None

    # 5️⃣ Désignation = tout entre ref et qty
    desig_zone = line.replace(ref, "", 1)
    for n in [qty, pu, montant]:
        desig_zone = desig_zone.replace(n, "")
    designation = desig_zone.strip()

    if debug:
        print(f"✅ Acceptée → Ref={ref} | Désignation={designation} | Qté={qty_f} | PU={pu_f} | Total={montant_f}")

    return {
        "ref": ref,
        "designation": designation,
        "qty": qty_f,
        "price_unit": pu_f,
        "total": montant_f,
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
        print(f"\n📄 --- Analyse page {page['page']} ---")
        table_lines = extract_table_lines(page.get("phrases", []))
        for l in table_lines:
            parsed = parse_table_line(l, debug=True)
            if parsed:
                all_lines.append(parsed)

    print("\n✅ Lignes de facture retenues :")
    print(json.dumps(all_lines, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
