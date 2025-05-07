import sys
import os
import pandas as pd

# 🛠️ Config Odoo
sys.path.append('/data/odoo/metal-odoo18-p8179')
os.environ['ODOO_RC'] = '/data/odoo/metal-odoo18-p8179/odoo18.conf'

import odoo
from odoo import api, tools, sql_db

# ⚙️ Initialisation Odoo
tools.config.parse_config()
odoo.service.server.load_server_wide_modules()
db = sql_db.db_connect('metal-prod-18')
cr = db.cursor()
env = api.Environment(cr, 1, {})

try:
    # 🎯 Entrées interactives
    csv_path_input = input("📄 Entrez le chemin du fichier CSV à importer : ").strip()
    CSV_PATH = csv_path_input

    template_id = int(input("🔍 Entrez l'ID du produit principal (product.template) : "))
    template = env['product.template'].browse(template_id)
    if not template or not template.exists():
        raise Exception("❌ Template introuvable.")

    # 🔍 Attribut dynamique
    attribute_name = f"Dimensions {template.name}"
    attribute = env['product.attribute'].search([('name', '=', attribute_name)], limit=1)
    if not attribute:
        attribute = env['product.attribute'].create({
            'name': attribute_name,
            'create_variant': 'always'
        })

    # 📀 Unité ML
    ml_uom = env['uom.uom'].search([('name', '=', 'ML')], limit=1)
    if not ml_uom:
        raise Exception("❌ Unité 'ML' introuvable.")

    # 📅 Lecture CSV
    df = pd.read_csv(CSV_PATH)
    value_ids = []

    for index, row in df.iterrows():
        code = str(row['default_code'])
        name = row['name']
        width = float(row['width']) if not pd.isna(row['width']) else 0.0
        height = float(row['height']) if not pd.isna(row['height']) else 0.0
        thickness = float(row['thickness']) if 'thickness' in row and not pd.isna(row['thickness']) else 0.0
        length = float(row['length']) if not pd.isna(row['length']) else 0.0

        # 🔀 Produit existant ?
        existing = env['product.product'].search([('default_code', '=', code)], limit=1)
        if existing:
            print(f"✏️ Produit existant : {code} → mise à jour")
            existing.write({
                'name': name,
                'product_width': width,
                'product_height': height,
                'product_thickness': thickness,
                'product_length': length,
                'dimensional_uom_id': ml_uom.id
            })
        else:
            # ➕ Création de valeur d’attribut si nécessaire
            value = env['product.attribute.value'].search([
                ('name', '=', name),
                ('attribute_id', '=', attribute.id)
            ], limit=1)
            if not value:
                value = env['product.attribute.value'].create({
                    'name': name,
                    'attribute_id': attribute.id,
                    'sequence': index
                })

            value_ids.append((code, value.id))

    # 🔗 Lien attributs au template
    if value_ids:
        print("🧩 Association des nouvelles valeurs au template...")
        template.write({
            'attribute_line_ids': [(0, 0, {
                'attribute_id': attribute.id,
                'value_ids': [(6, 0, [v[1] for v in value_ids])],
            })]
        })

    # 💡 Forcer la création des variantes
    template._create_variant_ids()

    # 🔀 Mise à jour des default_code sur les nouvelles variantes
    for variant in template.product_variant_ids:
        attrs = variant.product_template_attribute_value_ids.mapped('name')
        matched_code = next((code for code, val_id in value_ids if val_id in variant.product_template_attribute_value_ids.mapped('product_attribute_value_id').ids), None)
        if matched_code:
            variant.default_code = matched_code
            print(f"✅ Variante créée : {variant.name} → {variant.default_code}")

    cr.commit()
    print("\n✅ Import terminé avec succès !")

except Exception as e:
    cr.rollback()
    print("\n❌ Erreur :", e)

finally:
    cr.close()
