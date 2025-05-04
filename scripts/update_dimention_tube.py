import sys
import os
import csv

sys.path.append('/data/odoo/metal-odoo18-p8179')
os.environ['ODOO_RC'] = '/data/odoo/metal-odoo18-p8179/odoo18.conf'

import odoo
from odoo import api, tools, sql_db

DB = 'metal-prod-18'

# Initialisation
print("\U0001f527 Initialisation d'Odoo...")
tools.config.parse_config()
odoo.service.server.load_server_wide_modules()
db = sql_db.db_connect(DB)
cr = db.cursor()
env = api.Environment(cr, 1, {})  # Superadmin

# Demande du fichier CSV
csv_path = input("\U0001f5c2️  Chemin du fichier CSV : ").strip()
csv_filename = os.path.basename(csv_path).rsplit('.', 1)[0]  # nom du fichier sans extension

updated_products = set()
not_found_codes = []

try:
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        print(f"\n\U0001f4c4 Lecture du fichier CSV... Champs détectés : {reader.fieldnames}\n")

        for row in reader:
            default_code = row.get('default_code', '').strip()
            name = row.get('name', '').strip()
            print(f"\U0001f50d Recherche du produit {default_code} ({name})")

            try:
                length = float(row['length'])
                width = float(row['width'])
                height = float(row['height'])
                thickness = float(row['thickness'])
                uom_name = row['dimensional_uom'].strip()
            except Exception as err:
                print(f"⚠️ Erreur de parsing sur la ligne {default_code} : {err}")
                continue

            product = env['product.product'].search([('default_code', '=', default_code)], limit=1)
            if product:
                # Recherche de l'unité de mesure
                uom = env['uom.uom'].search([('name', '=', uom_name)], limit=1)

                vals = {
                    'product_length': length,
                    'product_width': width,
                    'product_height': height,
                    'product_thickness': thickness,
                    'dimensional_uom_id': uom.id if uom else False,
                }

                success = product.write(vals)
                updated_products.add(product.id)
                print(f"✅ {default_code} mis à jour : L={length} W={width} H={height} Ep={thickness} UoM={uom_name} (écrit={success})")
            else:
                print(f"❌ Produit introuvable pour default_code : {default_code}")
                not_found_codes.append(default_code)

        cr.commit()
        print("\n✅ Mise à jour terminée avec succès.")

        if updated_products:
            print("\n📋 Récapitulatif des produits modifiés :")
            products = env['product.product'].browse(list(updated_products))
            for p in products:
                print(f"\U0001f527 {p.default_code} → L={p.product_length} W={p.product_width} H={p.product_height} Ep={p.product_thickness} UoM={p.dimensional_uom_id.name}")
        else:
            print("📭 Aucun produit n'a été modifié.")

        if not_found_codes:
            print("\n❌ Default codes non trouvés :")
            for code in not_found_codes:
                print(f" - {code}")

except FileNotFoundError:
    print(f"❌ Fichier non trouvé : {csv_path}")
except Exception as e:
    cr.rollback()
    print("\n❌ Erreur générale :", e)
finally:
    cr.close()
