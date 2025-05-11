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
env.context = dict(env.context, lang='fr_FR')  # 🟢 force la langue française
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

    # 💼 Liste des produits dans la catégorie ID 6 (Métal au mètre)
    products = env['product.template'].search([('categ_id', '=', 6)])

    if not products:
        raise Exception("❌ Aucun produit trouvé dans la catégorie 'Métal au mètre'.")

    print("\n📊 Produits (templates) dans la catégorie 'Métal au mètre' :")
    for p in products:
        print(f" - ID: {p.id} | Nom: {p.name}")
        
    template_id = int(input("\n🔍 Copiez-collez l'ID du produit principal : "))
    template = env['product.template'].browse(template_id)
    if not template or not template.exists():
        raise Exception("❌ Template introuvable.")

    # 🔍 Liste des attributs disponibles
    all_attributes = env['product.attribute'].search([])
    print("\n🎛️ Attributs disponibles dans Odoo :")
    for attr in all_attributes:
        print(f" - ID: {attr.id} | Nom: {attr.name}")

    attribute_id = int(input("\n🧩 Entre l'ID de l'attribut à utiliser pour créer les variantes : "))
    attribute = env['product.attribute'].browse(attribute_id)
    if not attribute or not attribute.exists():
        raise Exception("❌ Attribut introuvable.")

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
            existing.write(dimensions_by_code[code])
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

    # 🧹 Mise à jour ou ajout de la ligne d'attribut proprement
    if value_ids:
        value_id_list = [v[1] for v in value_ids]
        line = template.attribute_line_ids.filtered(lambda l: l.attribute_id.id == attribute.id)
        if line:
            line.write({'value_ids': [(6, 0, value_id_list)]})
        else:
            template.write({
                'attribute_line_ids': [(0, 0, {
                    'attribute_id': attribute.id,
                    'value_ids': [(6, 0, value_id_list)]
                })]
            })

    # 🔄 Mise à jour des variantes
    for variant in template.product_variant_ids:
        matched_code = next(
            (code for code, val_id in value_ids
             if val_id in variant.product_template_attribute_value_ids.mapped('product_attribute_value_id').ids),
            None
        )
    new_name = f"{template.name} {dimensions_by_code[matched_code]['name']}"
    variant.write({
        'default_code': matched_code,
        'name': new_name,
        **dimensions_by_code[matched_code]
    })
    print(f"✅ Variante mise à jour : {variant.name} → {matched_code}")

    cr.commit()
    print("\n✅ Import terminé avec succès !")

except Exception as e:
    cr.rollback()
    print("\n❌ Erreur :", e)

finally:
    cr.close()
