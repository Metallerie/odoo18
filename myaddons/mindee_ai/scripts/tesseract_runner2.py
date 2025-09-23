import sys
import json
from pdf2image import convert_from_path
import pytesseract
import re

def extract_text_from_pdf(pdf_path):
    pages = convert_from_path(pdf_path)
    results = []
    for page_number, page in enumerate(pages, start=1):
        text = pytesseract.image_to_string(page, lang="fra")
        phrases = [line.strip() for line in text.splitlines() if line.strip()]
        results.append({
            "page": page_number,
            "phrases": phrases
        })
    return results

def looks_like_reference(text):
    """Détecte si une ligne commence par une référence produit (ex: alphanum ou chiffres)."""
    return bool(re.match(r"^[A-Z0-9]{2,}", text))

def clean_table(headers, lines):
    clean_headers = [h for h in headers if h != "|"]  # 🔹 supprime les barres verticales

    structured_lines = []
    current_line = None

    for raw in lines:
        # Supprime les barres verticales dans les données
        cols = [c.strip() for c in raw.split(" ") if c.strip() and c != "|"]

        # Reconstitue une phrase pour vérifier
        phrase = " ".join(cols)

        if looks_like_reference(phrase):
            # Si on a une ref → on commence une nouvelle ligne
            if current_line:
                structured_lines.append(current_line)
            current_line = {
                "ref": cols[0],
                "description": " ".join(cols[1:]),
                "quantity": "",
                "unit_price": "",
                "total_ht": "",
                "tva": ""
            }
        elif current_line:
            # Ligne sans ref → ajout à la désignation
            current_line["description"] += " " + phrase
        else:
            # Bruit → ignoré
            continue

    if current_line:
        structured_lines.append(current_line)

    return {
        "headers": clean_headers,
        "lines": structured_lines
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 tesseract_runner2.py <pdf_file>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    raw_pages = extract_text_from_pdf(pdf_path)

    output = {"pages": []}
    for page in raw_pages:
        phrases = page["phrases"]

        # Cherche une entête de tableau
        headers = []
        table_lines = []
        in_table = False

        for phrase in phrases:
            if any(word in phrase for word in ["Désignation", "Réf", "Prix Unitaire", "Montant"]):
                headers = [h for h in re.split(r"\s+", phrase) if h]
                in_table = True
                continue

            if in_table:
                if len(phrase.split()) < 2:  # trop court = fin probable du tableau
                    in_table = False
                else:
                    table_lines.append(phrase)

        table = clean_table(headers, table_lines)

        output["pages"].append({
            "page": page["page"],
            "normal_phrases": [p for p in phrases if p not in table_lines and p not in headers],
            "table": table
        })

    print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
