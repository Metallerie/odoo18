import sys
import json
import pytesseract
from pdf2image import convert_from_path
import re

def ocr_page(pdf_path):
    images = convert_from_path(pdf_path)
    results = []
    for img in images:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, lang="fra")
        words = []
        for i in range(len(data["text"])):
            if data["text"][i].strip():
                words.append({
                    "text": data["text"][i],
                    "left": data["left"][i],
                    "top": data["top"][i],
                    "width": data["width"][i],
                    "height": data["height"][i],
                })
        results.append(words)
    return results

def get_column_bounds(words):
    headers = {}
    for w in words:
        txt = w["text"].lower()
        if "réf" in txt:
            headers["Réf."] = w["left"]
        elif "désign" in txt:
            headers["Désignation"] = w["left"]
        elif "qté" in txt:
            headers["Qté"] = w["left"]
        elif "unité" in txt:
            headers["Unité"] = w["left"]
        elif "prix" in txt:
            headers["Prix Unitaire"] = w["left"]
        elif "montant" in txt:
            headers["Montant"] = w["left"]
        elif "tva" in txt:
            headers["TVA"] = w["left"]

    headers_sorted = dict(sorted(headers.items(), key=lambda x: x[1]))
    return list(headers_sorted.keys()), list(headers_sorted.values())

def map_row_to_columns(words, headers, bounds):
    row = {h: "" for h in headers}
    for w in words:
        x = w["left"]
        for i, h in enumerate(headers):
            if i == len(bounds) - 1 or (x >= bounds[i] and x < bounds[i+1]):
                row[h] += " " + w["text"]
                break
    return {k: v.strip() for k, v in row.items()}

def extract_table(words):
    # Cherche l'entête
    header_words = [w for w in words if re.search(r"(Réf|Désign|Qté|Montant|TVA)", w["text"], re.I)]
    if not header_words:
        return [], []

    headers, bounds = get_column_bounds(header_words)

    # Trie les mots par ligne
    words_sorted = sorted(words, key=lambda x: (x["top"], x["left"]))
    rows = []
    current_line_y = None
    current_words = []

    for w in words_sorted:
        if current_line_y is None:
            current_line_y = w["top"]
        if abs(w["top"] - current_line_y) > 15:  # saut de ligne
            if current_words:
                rows.append(map_row_to_columns(current_words, headers, bounds))
            current_words = [w]
            current_line_y = w["top"]
        else:
            current_words.append(w)
    if current_words:
        rows.append(map_row_to_columns(current_words, headers, bounds))

    return headers, rows

def main():
    if len(sys.argv) < 2:
        print("Usage: python tesseract_runner2.py <file.pdf>")
        return

    pdf_path = sys.argv[1]
    pages = ocr_page(pdf_path)

    output = {"pages": []}
    for i, words in enumerate(pages, start=1):
        headers, rows = extract_table(words)
        output["pages"].append({
            "page": i,
            "headers": headers,
            "products": rows
        })

    print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
