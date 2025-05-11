import sys
import os
import pandas as pd

# 🔧 Config Odoo
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
    # 📂 Liste des fichiers CSV dans le dossier
    CSV_DIR = '/data/odoo/metal-odoo18-p8179/csv'
    csv_files = [f for f in os.listdir(CSV_DIR) if f.endswith('.csv')]
    if not csv_files:
        raise Exception("❌ Aucun fichier CSV trouvé dans le dossier.")

    print("\n📄 Fichiers CSV disponibles :")
    for f in csv_files:
        print(f" - {f}")

    csv_filename = input("\n📄 Copiez-collez le nom du fichier CSV à importer : ").strip()
    CSV_PATH = os.path.join(CSV_DIR, csv_filename)

    # 💼 Liste des produits dans la catégorie ID 2
    products = env['product.template'].search([('categ_id', '=', 6)])
    if not products:
        raise Exception("❌ Aucun produit trouvé dans la catégorie 'Métal au mètre'.")

    print("\n📊 Produits disponibles dans 'Métal au mètre' :")
    for p in products:
        print(f" - ID: {p.id} | Nom: {p.name}")

    template_id = int(input("\n🔍 Copiez-collez l'ID du produit principal : "))
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

    # ⚠️ Mode de livraison activé ?
    delivery_enabled = env['ir.config_parameter'].sudo().get_param('stock.use_existing_lots')
    if delivery_enabled is None:
        print("⚠️ Impossible de vérifier si le mode de livraison est activé.")

    # 🔖 Lecture CSV
    df = pd.read_csv(CSV_PATH)
    value_ids = []
    dimensions_by_code = {}

    for index, row in df.iterrows():
        code = str(row['default_code'])
        name = row['name'].strip()
        diameter = float(row['diameter']) if not pd.isna(row['diameter']) else 0.0
        length = float(row['length']) if not pd.isna(row['length']) else 0.0
        width = float(row['width']) if not pd.isna(row['width']) else 0.0
        height = float(row['height']) if not pd.isna(row['height']) else 0.0
        thickness = float(row['thickness']) if 'thickness' in row and not pd.isna(row['thickness']) else 0.0


        dimensions_by_code[code] = {
            'name': name,
            'product_diameter': diameter,
            'product_length': length,
            'product_width': width,
            'product_height': height,
            'product_thickness': thickness,

        }

        # 🔄 Mise à jour si produit existe
        existing = env['product.product'].search([('default_code', '=', code)], limit=1)
        if existing:
            print(f"✏️ Produit existant : {code} → mise à jour")
            update_vals = {
                'name': name,
                'product_diameter': diameter,
                'product_thickness': thickness,
                'product_length': length,
                'product_width': width,
                'product_height': height,
                'product_thickness': thickness,

            }
           

            existing.write(update_vals)
           
            continue

        # ➕ Création valeur d'attribut si nécessaire
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

    # 🧹 Association des valeurs au template
    if value_ids:
        print("🧹 Association des nouvelles valeurs au template...")
        template.write({
            'attribute_line_ids': [(0, 0, {
                'attribute_id': attribute.id,
                'value_ids': [(6, 0, [v[1] for v in value_ids])],
            })]
        })

    # 💫 Création des variantes
    template._create_variant_ids()

    # 🔄 Mise à jour des nouvelles variantes
    for variant in template.product_variant_ids:
        matched_code = next(
            (code for code, val_id in value_ids
             if val_id in variant.product_template_attribute_value_ids.mapped('product_attribute_value_id').ids),
            None
        )
        if matched_code and matched_code in dimensions_by_code:
            dims = dimensions_by_code[matched_code]
            update_vals = {
                'default_code': matched_code,
                'name': dims['name'],
                'product_diameter': dims['product_diameter'],
                'product_length': dims['product_length'],
                'product_width': dims['product_width'],
                'product_height': dims['product_height'],
                'product_thickness': dims['product_thickness'],
            }
            
            variant.write(update_vals)
            
            print(f"✅ Variante créée : {variant.name} → {variant.default_code}")

    cr.commit()
    print("\n✅ Import terminé avec succès !")

except Exception as e:
    cr.rollback()
    print("\n❌ Erreur :", e)

finally:
    cr.close()
