
#!/usr/bin/env python3
import sys
import json
import os
from pdf2image import convert_from_path
import pytesseract
from pytesseract import Output
from tempfile import TemporaryDirectory


def extract_tables(lines):
    """Détection simple des tableaux dans le texte OCR."""
    tables = []
    current_table = []

    for line in lines:
        # Heuristique : une ligne avec beaucoup d'espaces ou des '|'
        if line.count(" ") > 6 or "|" in line:
            # On découpe par espace ou pipe
            cols = [col.strip() for col in line.replace("|", " ").split() if col.strip()]
            current_table.append(cols)
        else:
            if current_table:
                tables.append(current_table)
                current_table = []
    if current_table:
        tables.append(current_table)

    return tables


def main(pdf_path):
    if not os.path.exists(pdf_path):
        print(json.dumps({"error": f"Fichier introuvable: {pdf_path}"}))
        sys.exit(1)

    print(f"📥 Lecture du fichier : {pdf_path}", file=sys.stderr)

    data = {"pages": []}

    with TemporaryDirectory() as tempdir:
        print("🖼️ Conversion PDF -> PNG...", file=sys.stderr)
        images = convert_from_path(pdf_path, dpi=300, output_folder=tempdir)

        for i, img in enumerate(images, start=1):
            print(f"🔎 OCR avec Tesseract sur page {i}...", file=sys.stderr)
            text = pytesseract.image_to_string(img, lang="fra")

            # Découpe en phrases (par ligne)
            phrases = [line.strip() for line in text.split("\n") if line.strip()]

            # Extraction brute de tableaux
            tables = extract_tables(phrases)

            page_data = {
                "page": i,
                "content": text,
                "phrases": phrases,
                "tables": tables
            }
            data["pages"].append(page_data)

    print("✅ OCR terminé", file=sys.stderr)
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: tesseract_runner.py <fichier.pdf>", file=sys.stderr)
        sys.exit(1)

    main(sys.argv[1])
