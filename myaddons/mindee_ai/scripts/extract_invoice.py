# -*- coding: utf-8 -*-
import sys
import json
import logging

def print_separator(char="=", width=66):
    print(char * width)

def format_line(cols, widths):
    """Formate une ligne en fonction des largeurs"""
    return "  ".join(str(c).ljust(w) for c, w in zip(cols, widths))

def render_ascii(invoice):
    # === HEADER ===
    print_separator("=")
    print(f"{'FACTURE N° : ' + invoice.get('invoice_number', 'NUL')}".center(66))
    print(f"Date : {invoice.get('invoice_date', 'NUL')}".center(66))
    print_separator("-")
    print(f"Client : {invoice.get('client_id','NUL')}".ljust(30) + 
          f"SIREN : {invoice.get('siren','NUL')}".rjust(30))
    print("Adresse de Facturation".ljust(33) + "Adresse de Livraison")
    print(invoice.get("billing_address","NUL").ljust(33) + invoice.get("shipping_address","NUL"))
    print_separator("-")

    # === TABLEAU ===
    headers = ["Réf.", "Désignation", "Qté", "Unité", "PU", "Montant", "TVA"]
    widths = [8, 28, 5, 6, 8, 8, 5]
    print(format_line(headers, widths))
    print("-" * 66)

    rows = invoice.get("lines", [])
    if not rows:
        print("Aucune ligne de produit trouvée.")
    else:
        for row in rows:
            print(format_line([
                row.get("reference","NUL"),
                row.get("description","NUL"),
                row.get("quantity","NUL"),
                row.get("unit","NUL"),
                row.get("unit_price","NUL"),
                row.get("amount_ht","NUL"),
                row.get("vat","NUL")
            ], widths))
    print("-" * 66)

    # === TOTALS ===
    print(f"{'TOTAL BRUT HT :':>50} {invoice.get('total_brut_ht','NUL')}")
    print(f"{'TOTAL ECO-PART :':>50} {invoice.get('eco_part','NUL')}")
    print(f"{'TOTAL NET HT   :':>50} {invoice.get('total_ht','NUL')}")
    print(f"{'TOTAL T.V.A.   :':>50} {invoice.get('total_tva','NUL')}")
    print_separator("-")
    print(f"{'NET A PAYER    :':>50} {invoice.get('total_ttc','NUL')} €")
    print_separator("=")

    # === FOOTER ===
    print("\nConditions de paiement :")
    print(invoice.get("payment_method", "NUL"))
    print("\nMentions légales :")
    print(invoice.get("mentions","NUL"))
    print("\nSociété émettrice :")
    print(invoice.get("supplier","NUL"))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_invoice.py <json_file>")
        sys.exit(1)

    json_file = sys.argv[1]
    with open(json_file, "r", encoding="utf-8") as f:
        invoice = json.load(f)

    render_ascii(invoice)
