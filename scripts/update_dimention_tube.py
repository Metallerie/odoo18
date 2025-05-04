import sys
import os
import csv

sys.path.append('/data/odoo/metal-odoo18-p8179')
os.environ['ODOO_RC'] = '/data/odoo/metal-odoo18-p8179/odoo18.conf'

import odoo
from odoo import api, tools, sql_db

DB = 'metal-prod-18'

# Initialisation
print("🔧 Initialisation d'Odoo...")
tools.config.parse_config()
odoo.service.server.load_server_wide_modules()
db = sql_db.db_connect(DB)
cr = db.cursor()
env = api.Environment(cr, 1, {})  # Superadmin

# Demande du fichier CSV
csv_path = input("🗂️  Chemin du fichier CSV : ").strip()

updated_templates = set()
not_found_codes = []

try:
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)  # CSV standard (séparateur virgule)
        print(f"\n📄 Lecture du fichier CSV... Champs détectés : {reader.fieldnames}\n")

        for row in reader:
            default_code = row.get('default_code', '').strip()
            name = row.get('name', '').strip()
            print(f"🔍 Recherche du produit {default_code} ({name})")

            try:
                length = float(row['length'])
                width = float(row['width'])
                height = float(row['height'])
                thickness = float(row['thickness'])
                uom_name = row['dimensional_uom'].strip()
            except Exception as err:
                print(f"⚠️ Erreur de parsing sur la ligne {default_code} : {err}")
                continue

            products = env['product.product'].search([])
            product = next((p for p in products if (p.default_code or '').strip() == default_code), None)
            if product:
                tmpl = product.product_tmpl_id

                # Recherche de l'unité de mesure
                uom = env['uom.uom'].search([('name', '=', uom_name)], limit=1)

                vals = {
                    'product_length': length,
                    'product_width': width,
                    'product_height': height,
                    'product_thickness': thickness,
                    'dimensional_uom_id': uom.id if uom else False,
                }

                tmpl.write(vals)
                updated_templates.add(tmpl.id)
                print(f"✅ {default_code} mis à jour : L={length} W={width} H={height} Ep={thickness} UoM={uom_name}")
            else:
                print(f"❌ Produit introuvable pour default_code : {default_code}")
                not_found_codes.append(default_code)

        cr.commit()
        print("\n✅ Mise à jour terminée avec succès.")

        # Afficher les enregistrements modifiés
        if updated_templates:
            print("\n📋 Récapitulatif des templates modifiés :")
            templates = env['product.template'].browse(list(updated_templates))
            for t in templates:
                print(f"🔧 {t.name} → L={t.product_length} W={t.product_width} H={t.product_height} Ep={t.product_thickness} UoM={t.dimensional_uom_id.name}")
        else:
            print("📭 Aucun template n'a été modifié.")

        # Afficher les default_code non trouvés
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
