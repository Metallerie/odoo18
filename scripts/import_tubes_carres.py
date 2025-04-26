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

    # Récupération du template de base
    template = env['product.template'].browse(7)
    if not template:
        raise Exception("Template ID 7 introuvable.")

    # Récupération de l'unité ML
    ml_uom = env['uom.uom'].search([('name', '=', 'ML')], limit=1)
    if not ml_uom:
        raise Exception("Unité de mesure 'ML' introuvable.")

    # Récupération ou création de l'attribut "Dimensions Tube"
    attribute = env['product.attribute'].search([('name', '=', 'Dimensions Tube')], limit=1)
    if not attribute:
        attribute = env['product.attribute'].create({'name': 'Dimensions Tube', 'create_variant': 'always'})

    # Liste pour stocker les valeurs
    value_ids = []

    # Création des valeurs d'attribut
    for index, row in df.iterrows():
        name = row['name'].replace(' mm', '').replace(' ', '')  # Nettoyage du nom
        value = env['product.attribute.value'].search([
            ('name', '=', name),
            ('attribute_id', '=', attribute.id)
        ], limit=1)
        if not value:
            value = env['product.attribute.value'].create({
                'name': name,
                'attribute_id': attribute.id,
            })
        value_ids.append(value.id)

    # Association de l'attribut au template
    template.write({
        'attribute_line_ids': [(0, 0, {
            'attribute_id': attribute.id,
            'value_ids': [(6, 0, value_ids)],
        })]
    })

    print("✅ Attribut et variantes créés")

    # Maintenant on met à jour chaque variante
    for variant in template.product_variant_ids:
        variant_name = variant.product_template_attribute_value_ids[0].name
        match = df[df['name'].str.replace(' ', '').str.replace('mm', '') == variant_name]
        if not match.empty:
            row = match.iloc[0]
            variant.default_code = row['default_code']

            tmpl = variant.product_tmpl_id
            tmpl.product_width = round(row['width'], 6)
            tmpl.product_height = round(row['height'], 6)
            tmpl.product_thickness = round(row['thickness'], 6)
            tmpl.product_length = round(row['length'], 6)
            tmpl.dimensional_uom_id = ml_uom.id

            print(f"✅ Variante mise à jour : {variant_name}")

    cr.commit()
    print("\n✅ Import complet terminé avec succès !")

except Exception as e:
    cr.rollback()
    print("\n❌ Erreur :", e)

finally:
    cr.close()
