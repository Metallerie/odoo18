#!/usr/bin/env python3
import sys
import pytesseract
from pytesseract import Output
from pdf2image import convert_from_path
import re
import json

def ocr_with_structure(pdf_path):
    # Convertir PDF -> images
    pages = convert_from_path(pdf_path)
    results = []

    for page_num, page in enumerate(pages, start=1):
        data = pytesseract.image_to_data(page, output_type=Output.DICT, lang="fra")
        width, height = page.size
        header, body, footer = [], [], []

        for i, text in enumerate(data["text"]):
            if not text.strip():
                continue
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            box = {"text": text, "x": x, "y": y, "w": w, "h": h}
            if y < height * 0.25:
                header.append(box)
            elif y > height * 0.75:
                footer.append(box)
            else:
                body.append(box)

        results.append({
            "page": page_num,
            "header": " ".join([b["text"] for b in header]),
            "body": " ".join([b["text"] for b in body]),
            "footer": " ".join([b["text"] for b in footer])
        })
    return results


def parse_invoice(zones):
    parsed = {}
    header = zones["header"]
    body = zones["body"]
    footer = zones["footer"]

    # --- HEADER ---
    if m := re.search(r"FACTURE\s*N°\s*[: ]\s*(\d+)", header, re.I):
        parsed["invoice_number"] = m.group(1)

    if m := re.search(r"Date facture\s*[: ]\s*([\d/]+)", header, re.I):
        parsed["invoice_date"] = m.group(1)

    if m := re.search(r"Client\s*[: ]\s*(\d+)", header, re.I):
        parsed["client_id"] = m.group(1)

    if m := re.search(r"MR\s+([A-Z ]+)", header, re.I):
        parsed["client_name"] = m.group(0)

    # --- FOOTER ---
    if m := re.search(r"SIREN\s+(\d+)", footer):
        parsed["siren"] = m.group(1)

    if m := re.search(r"IBAN\s+([A-Z0-9 ]+)", footer):
        parsed["iban"] = m.group(1).replace(" ", "")

    if m := re.search(r"BIC\s*[: ]\s*([A-Z0-9]+)", footer):
        parsed["bic"] = m.group(1)

    if m := re.search(r"NET À PAYER\s+([\d,.]+)", footer, re.I):
        parsed["total_ttc"] = m.group(1)

    if m := re.search(r"TOTAL NET HT\s+([\d,.]+)", footer, re.I):
        parsed["total_ht"] = m.group(1)

    if m := re.search(r"TOTAL T\.V\.A\.\s+([\d,.]+)", footer, re.I):
        parsed["total_tva"] = m.group(1)

    if "Comptoir Commercial du Languedoc" in footer:
        parsed["fournisseur"] = "Comptoir Commercial du Languedoc"

    # --- BODY (simplifié : on découpe par motif "ref + texte + prix") ---
    line_items = []
    lines = re.findall(r"(\d{4,})\s+([A-Z0-9\- ]+)\s+(\d+)\s+PI\s+([\d,.]+)\s+([\d,.]+)", body)
    for ref, designation, qty, pu, montant in lines:
        line_items.append({
            "ref": ref,
            "designation": designation.strip(),
            "qty": int(qty),
            "unit_price": pu,
            "amount": montant
        })

    if line_items:
        parsed["line_items"] = line_items

    return parsed


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 tesseract_runner4.py <fichier.pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"📥 Lecture du fichier : {pdf_path}")

    structured = ocr_with_structure(pdf_path)

    enriched = []
    for page in structured:
        parsed = parse_invoice(page)
        enriched.append({"page": page["page"], "parsed": parsed})

    print("✅ OCR + parsing terminé")
    print(json.dumps(enriched, indent=2, ensure_ascii=False))
