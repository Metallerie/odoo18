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

def parse_table_line(line, debug=False):
    """Découpe une ligne en colonnes, retourne facture OU commentaire."""
    parts = line.split()
    ref = parts[0]

    # 1️⃣ Vérifie que le "ref" ressemble à un code article
    if not re.match(r"^[A-Za-z0-9\-]+$", ref):
        if debug:
            print(f"ℹ️ Commentaire (pas de réf valide) → {line}")
        return {"type": "commentaire", "raw": line}

    # 2️⃣ Récupère les nombres
    nums = re.findall(r"\d+[,.]?\d*", line)
    if len(nums) < 4:
        if debug:
            print(f"ℹ️ Commentaire (pas assez de nombres) → {line}")
        return {"type": "commentaire", "raw": line}

    qty, pu, montant, tva = nums[-4], nums[-3], nums[-2], nums[-1]

    # 3️⃣ Convertit en float
    try:
        qty_f = float(qty.replace(",", "."))
        pu_f = float(pu.replace(",", "."))
        montant_f = float(montant.replace(",", "."))
        tva_f = float(tva.replace(",", "."))
    except ValueError:
        if debug:
            print(f"ℹ️ Commentaire (conversion impossible) → {line}")
        return {"type": "commentaire", "raw": line}

    # 4️⃣ Vérifie cohérence PU * Qté ≈ Montant
    if not (abs((qty_f * pu_f) - montant_f) < max(0.05, 0.01 * montant_f)):
        if debug:
            print(f"ℹ️ Commentaire (incohérence: {qty_f}*{pu_f} != {montant_f}) → {line}")
        return {"type": "commentaire", "raw": line}

    # 5️⃣ Désignation = tout entre ref et qty
    desig_zone = line.replace(ref, "", 1)
    for n in [qty, pu, montant, tva]:
        desig_zone = desig_zone.replace(n, "")
    designation = desig_zone.strip()

    if debug:
        print(f"✅ Facture → Ref={ref} | Désignation={designation} | Qté={qty_f} | PU={pu_f} | Total={montant_f} | TVA={tva_f}")

    return {
        "type": "facture",
        "ref": ref,
        "designation": designation,
        "qty": qty_f,
        "price_unit": pu_f,
        "total": montant_f,
        "tva": tva_f,
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

    results = []
    for page in ocr_data.get("pages", []):
        print(f"\n📄 --- Analyse page {page['page']} ---")
        table_lines = extract_table_lines(page.get("phrases", []))
        for l in table_lines:
            parsed = parse_table_line(l, debug=True)
            results.append(parsed)

    print("\n📊 Résultat final (factures + commentaires) :")
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
