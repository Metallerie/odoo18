import subprocess
import sys
import json
import os

if len(sys.argv) != 2:
    print("Usage: python3 tesseract_runner.py <chemin_du_pdf>")
    sys.exit(1)

pdf_path = sys.argv[1]
print(f"📥 Lecture du fichier : {pdf_path}")

# 1. Convertir le PDF en PNG
print("🖼️ Conversion PDF -> PNG...")
try:
    subprocess.run(
        ["pdftoppm", "-png", pdf_path, "/tmp/tesseract_page"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
except subprocess.CalledProcessError as e:
    print("❌ Erreur lors de pdftoppm :", e.stderr.decode("utf-8"))
    sys.exit(1)

# 2. OCR sur chaque page
print("🔎 OCR avec Tesseract...")
text_pages = []
page_idx = 1

while True:
    img_file = f"/tmp/tesseract_page-{page_idx:01d}.png"
    if not os.path.exists(img_file):
        break

    try:
        result = subprocess.run(
            ["tesseract", img_file, "stdout", "-l", "fra"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8"
        )
        text_pages.append({"page": page_idx, "content": result.stdout})
        print(f"✅ Page {page_idx} traitée")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur Tesseract page {page_idx} :", e.stderr)
        break

    page_idx += 1

# 3. Afficher le JSON brut
output = {"pages": text_pages}
print(json.dumps(output, ensure_ascii=False, indent=2))
