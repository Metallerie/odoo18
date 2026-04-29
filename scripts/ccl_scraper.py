# -*- coding: utf-8 -*-
# ccl_scraper.py

import csv
import os
import re
from getpass import getpass

from playwright.sync_api import sync_playwright


CSV_DIR = "/data/odoo/metal-odoo18-p8179/csv"
LOGIN_URL = "https://pro.ccl.fr/identification"
EMAIL = "franckbardina@free.fr"


def extract_float(value, default=0.0):
    try:
        value = str(value or "").replace("\xa0", " ").replace(",", ".").strip()
        value = re.sub(r"[^\d.]", "", value)
        return float(value) if value else default
    except Exception:
        return default


def extract_dimensions(name):
    """
    Exemple :
    Tube soudés rectangulaire 30x20x2 longueur 6,15 m
    -> height=0.03, width=0.02, thickness=0.002, length=6.15
    """
    height = ""
    width = ""
    thickness = ""
    length = ""

    dim_match = re.search(
        r"(\d+(?:[.,]\d+)?)x(\d+(?:[.,]\d+)?)x(\d+(?:[.,]\d+)?)",
        name,
        re.IGNORECASE,
    )
    if dim_match:
        height = extract_float(dim_match.group(1)) / 1000
        width = extract_float(dim_match.group(2)) / 1000
        thickness = extract_float(dim_match.group(3)) / 1000

    length_match = re.search(
        r"longueur\s+(\d+(?:[.,]\d+)?)\s*m",
        name,
        re.IGNORECASE,
    )
    if length_match:
        length = extract_float(length_match.group(1))

    return height, width, length, thickness


def clean_product_name(name):
    name = re.sub(r"\s+", " ", name or "").strip()
    name = re.sub(r"\s+longueur\s+\d+(?:[.,]\d+)?\s*m", "", name, flags=re.I)
    return name


def normalize_purchase_unit(name, uom_code):
    name_lower = (name or "").lower()

    if "tube" in name_lower:
        return "Tube"
    if "corni" in name_lower:
        return "Barre"
    if "fer plat" in name_lower or "plat" in name_lower:
        return "Barre"

    if uom_code == "ML":
        return "Tube"

    return "Barre"


def main():
    csv_name = input("Nom du CSV : ").strip()
    page_url = input("URL page CCL : ").strip()
    password = getpass("Mot de passe : ")

    if not csv_name.lower().endswith(".csv"):
        csv_name += ".csv"

    csv_path = os.path.join(CSV_DIR, csv_name)
    os.makedirs(CSV_DIR, exist_ok=True)

    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Connexion...")

        page.goto(LOGIN_URL)
        page.wait_for_load_state("networkidle")

        page.fill("#email", EMAIL)
        page.fill("#password", password)
        page.click("button[type='submit']")

        page.wait_for_load_state("networkidle")

        print("Connexion OK")
        print("Ouverture page produit...")

        page.goto(page_url)
        page.wait_for_load_state("networkidle")

        articles = page.locator("div.article").all()
        print(f"Articles trouvés : {len(articles)}")

        for article in articles:
            try:
                raw_name = article.locator("span.title").inner_text().strip()
                name = clean_product_name(raw_name)
                text = article.inner_text()

                ref_match = re.search(r"Réf CCL\s*:\s*(\d+)", text)
                uom_match = re.search(r"Unité de vente\s*:\s*([A-Z]+)", text)
                factor_match = re.search(
                    r"Rapport\s*:\s*1\s*PI\s*=\s*([\d.,]+)\s*([A-Z]+)?",
                    text,
                    re.IGNORECASE,
                )
                price_match = re.search(
                    r"Prix net\s*([\d.,]+)\s*€",
                    text,
                    re.IGNORECASE,
                )

                if not ref_match or not price_match:
                    continue

                default_code = ref_match.group(1).strip()
                uom_code = uom_match.group(1).strip() if uom_match else "ML"
                factor = extract_float(factor_match.group(1), 1.0) if factor_match else 1.0
                price_net = extract_float(price_match.group(1))

                height, width, length, thickness = extract_dimensions(raw_name)

                if not length:
                    length = factor if factor else ""

                # Pour ton wizard : standard_price doit être dans l'unité Odoo.
                # Exemple : prix CCL 10.64 € pour 1 PI = 6.15 ML
                # => coût ML = 10.64 / 6.15
                standard_price = price_net
                if uom_code == "ML" and factor:
                    standard_price = price_net / factor

                purchase_unit = normalize_purchase_unit(name, uom_code)

                rows.append(
                    {
                        "default_code": default_code,
                        "name": name,
                        "height": height,
                        "width": width,
                        "length": length,
                        "thickness": thickness,
                        "uom_code": uom_code,
                        "factor": factor,
                        "standard_price": round(standard_price, 3),
                        "purchase_unit": purchase_unit,
                    }
                )

            except Exception as exc:
                print("Erreur article :", exc)
                continue

        browser.close()

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "default_code",
                "name",
                "height",
                "width",
                "length",
                "thickness",
                "uom_code",
                "factor",
                "standard_price",
                "purchase_unit",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Produits exportés : {len(rows)}")
    print(f"CSV créé : {csv_path}")


if __name__ == "__main__":
    main()
