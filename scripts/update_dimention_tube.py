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

try:
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        print(f"🧾 Champs détectés : {reader.fieldnames}")
        print("\n📄 Lecture du fichier CSV...")
      

        for row in reader:   
            print(row)  # 👈 à ajouter ici pour debug
            default_code = row['default_code'].strip()
            name = row['name'].strip()
            try:
                length = float(row['length'])
                width = float(row['width'])
                height = float(row['height'])
                thickness = float(row['thickness'])
                uom_name = row['dimensional_uom'].strip()
            except Exception as err:
                print(f"⚠️ Erreur de parsing sur la ligne {default_code} : {err}")
 #               continue

            product = env['product.product'].search([('default_code', '=', default_code)], limit=1)
            if product:
                tmpl = product.product_tmpl_id
                tmpl.product_length = length
                tmpl.product_width = width
                tmpl.product_height = height
                tmpl.product_thickness = thickness

                uom = env['uom.uom'].search([('name', '=', uom_name)], limit=1)
                if uom:
                    tmpl.dimensional_uom_id = uom.id

                print(f"✅ {default_code} - {name} mis à jour : L={length} W={width} H={height} Ep={thickness} UoM={uom_name}")
            else:
                print(f"❌ Produit introuvable pour default_code : {default_code}")

        cr.commit()
        print("\n✅ Mise à jour terminée avec succès.")

except FileNotFoundError:
    print(f"❌ Fichier non trouvé : {csv_path}")
except Exception as e:
    cr.rollback()
    print("\n❌ Erreur générale :", e)
finally:
    cr.close()
