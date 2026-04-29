# -*- coding: utf-8 -*-
#  ccl_scraper.py


import csv
import os
import re
from getpass import getpass
from playwright.sync_api import sync_playwright

CSV_DIR = "/data/odoo/metal-odoo18-p8179/csv"
EMAIL = "franckbardina@free.fr"


def extract_float(value):
    return float(value.replace(",", ".").strip())


def extract_dimensions(name):
    match = re.search(r"(\d+)x(\d+)x(\d+)", name)
    if not match:
        return "", "", "", ""

    h = float(match.group(1)) / 1000
    w = float(match.group(2)) / 1000
    t = float(match.group(3)) / 1000

    return h, w, t


def main():
    csv_name = input("Nom du CSV : ").strip()
    page_url = input("URL page CCL : ").strip()
    password = getpass("Mot de passe : ")

    if not csv_name.endswith(".csv"):
        csv_name += ".csv"

    csv_path = os.path.join(CSV_DIR, csv_name)

    os.makedirs(CSV_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Connexion...")

        page.goto("https://pro.ccl.fr")  # adapte si besoin

        page.fill("input[type='email']", EMAIL)
        page.fill("input[type='password']", password)
        page.click("button[type='submit']")

        page.wait_for_load_state("networkidle")

        print("OK")

        page.goto(page_url)
        page.wait_for_load_state("networkidle")

        articles = page.locator("div.article").all()

        rows = []

        for article in articles:
            try:
                name = article.locator("span.title").inner_text().strip()
                text = article.inner_text()

                ref_match = re.search(r"Réf CCL\s*:\s*(\d+)", text)
                uom_match = re.search(r"Unité de vente\s*:\s*([A-Z]+)", text)
                factor_match = re.search(r"Rapport\s*:\s*1\s*PI\s*=\s*([\d.,]+)", text)
                price_match = re.search(r"Prix net\s*([\d.,]+)\s*€", text)

                if not ref_match or not price_match:
                    continue

                default_code = ref_match.group(1)
                uom_code = uom_match.group(1) if uom_match else "ML"
                factor = extract_float(factor_match.group(1)) if factor_match else 1.0
                price = extract_float(price_match.group(1))

                # ⚠️ conversion prix barre → ML
                if factor > 1:
                    price = price / factor

                h, w, t = extract_dimensions(name)

                row = {
                    "default_code": default_code,
                    "name": name,
                    "height": h,
                    "width": w,
                    "length": factor,
                    "thickness": t,
                    "uom_code": uom_code,
                    "factor": factor,
                    "standard_price": round(price, 3),
                    "purchase_unit": "Tube" if uom_code == "ML" else "Barre",
                }

                rows.append(row)

            except Exception as e:
                print("Erreur ligne :", e)
                continue

        print(f"{len(rows)} produits récupérés")

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

        browser.close()

    print(f"CSV prêt : {csv_path}")


if __name__ == "__main__":
    main()
