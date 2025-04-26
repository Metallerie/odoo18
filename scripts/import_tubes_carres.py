import sys
import os
import pandas as pd

sys.path.append('/data/odoo/metal-odoo18-p8179')
os.environ['ODOO_RC'] = '/data/odoo/metal-odoo18-p8179/odoo18.conf'

import odoo
from odoo import api, tools, sql_db

DB = 'metal-prod-18'
CSV_PATH = '/data/odoo/metal-odoo18-p8179/csv/tubes_carres_correct_full.csv'

# Initialisation Odoo
tools.config.parse_config()
odoo.service.server.load_server_wide_modules()
db = sql_db.db_connect(DB)
cr = db.cursor()
env = api.Environment(cr, 1, {})

try:
    df = pd.read_csv(CSV_PATH)

    template = env['product.template'].browse(7)
    if not template:
        raise Exception("Template ID 7 introuvable.")

    ml_uom = env['uom.uom'].search([('name', '=', 'ML')], limit=1)
    if not ml_uom:
        raise Exception("Unité de mesure 'ML' introuvable.")

    for index, row in df.iterrows():
        default_code = row['default_code']
        name = row['name']

        product_width = row['width']
        product_height = row['height']
        product_thickness = row['thickness']
        product_length = row['length']

        new_variant = env['product.product'].create({
            'product_tmpl_id': template.id,
            'default_code': default_code,
            'name': name,
        })

        tmpl = new_variant.product_tmpl_id
        tmpl.product_width = round(product_width, 6)
        tmpl.product_height = round(product_height, 6)
        tmpl.product_thickness = round(product_thickness, 6)
        tmpl.product_length = round(product_length, 6)
        tmpl.dimensional_uom_id = ml_uom.id

        print(f"✅ Variante créée : {name}")

    cr.commit()
    print("\n✅ Import terminé avec succès !")

except Exception as e:
    cr.rollback()
    print("\n❌ Erreur :", e)

finally:
    cr.close()
