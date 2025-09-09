import sys
import os
import pandas as pd

# 🔧 Config Odoo
sys.path.append('/data/odoo/metal-odoo18-p8179')
os.environ['ODOO_RC'] = '/data/odoo/metal-odoo18-p8179/odoo18.conf'

import odoo
from odoo import api, tools, sql_db


def safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        s = str(x).strip().replace(',', '.')
        return float(s) if s else default
    except Exception:
        return default


# ⚙️ Initialisation Odoo
tools.config.parse_config([])
odoo.service.server.load_server_wide_modules()
db = sql_db.db_connect('metal-prod-18')
cr = db.cursor()
env = api.Environment(cr, 1, {})
env.context = dict(env.context, lang='fr_FR')

try:
    # 📂 CSV dispo
    CSV_DIR = '/data/odoo/metal-odoo18-p8179/csv'
    csv_files = [f for f in os.listdir(CSV_DIR) if f.endswith('.csv')]
    if not csv_files:
        raise Exception("❌ Aucun fichier CSV trouvé dans le dossier.")

    print("\n📄 Fichiers CSV disponibles :")
    for f in csv_files:
        print(f" - {f}")

    csv_filename = input("\n📄 Nom du fichier CSV à importer : ").strip()
    CSV_PATH = os.path.join(CSV_DIR, csv_filename)

    # 💼 Templates catégorie 6
    products = env['product.template'].search([('categ_id', '=', 6)])
    if not products:
        raise Exception("❌ Aucun produit trouvé dans la catégorie 'Métal au mètre'.")

    print("\n📊 Templates dans 'Métal au mètre' :")
    for p in products:
        print(f" - ID: {p.id} | Nom: {p.name}")

    template_id = int(input("\n🔍 ID du template principal : "))
    template = env['product.template'].browse(template_id)
    if not template or not template.exists():
        raise Exception("❌ Template introuvable.")

    # 🔍 Attribut
    all_attributes = env['product.attribute'].search([])
    print("\n🎛️ Attributs disponibles :")
    for attr in all_attributes:
        print(f" - ID: {attr.id} | Nom: {attr.name}")

    attribute_id = int(input("\n🧩 ID de l'attribut pour créer les variantes : "))
    attribute = env['product.attribute'].browse(attribute_id)
    if not attribute or not attribute.exists():
        raise Exception("❌ Attribut introuvable.")

    # 🔖 Lecture CSV
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip() for c in df.columns]  # normalise

    value_links = []           # [(default_code, attr_value_id)]
    dimensions_by_code = {}    # code -> dims + label
    label_by_code = {}         # code -> "40x4 mm"

    for index, row in df.iterrows():
        code = str(row.get('default_code', '')).strip()
        if not code:
            print(f"⚠️ Ligne {index}: default_code manquant → ignorée")
            continue

        label = str(row.get('name', '')).strip()

        diameter = safe_float(row.get('diameter', 0.0))
        length = safe_float(row.get('length', 0.0))
        width = safe_float(row.get('width', 0.0))
        height = safe_float(row.get('height', 0.0))
        thickness = safe_float(row.get('thickness', 0.0))

        # 🟢 Fer plat : l'épaisseur vient de 'height' si 'thickness' vaut 0
        if thickness == 0.0 and height > 0.0:
            thickness = height

        dims = {
            'product_diameter': diameter,
            'product_length': length,
            'product_width': width,
            'product_height': height,       # on conserve la valeur source
            'product_thickness': thickness  # utilisé par l'IHM/rapports
        }
        dimensions_by_code[code] = {'variant_label': label, **dims}
        label_by_code[code] = label

        # 🔄 Existant → update dimensions
        existing = env['product.product'].search([('default_code', '=', code)], limit=1)

        # ➕ valeur d'attribut (cherche ou crée)
        value = env['product.attribute.value'].search([
            ('name', '=', label),
            ('attribute_id', '=', attribute.id)
        ], limit=1)
        if not value:
            value = env['product.attribute.value'].create({
                'name': label,
                'attribute_id': attribute.id,
                'sequence': int(index)
            })

        # Conserver le mapping quoi qu'il arrive
        value_links.append((code, value.id))

        if existing:
            print(f"✏️ Produit existant : {code} → mise à jour dimensions")
            existing.write(dims)

    # 🧹 Aligner la ligne d'attribut sur le template
    if value_links:
        value_id_list = sorted({v_id for _, v_id in value_links})
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

    # Force refresh (variants auto-générées par Odoo à l'écriture des lignes d'attribut)
    template.invalidate_recordset()

    # 🔄 Mise à jour des variantes (code + nom + dimensions)
    # index inverse valeur_attribut_id -> default_code
    val_to_code = {}
    for code, v_id in value_links:
        val_to_code[v_id] = code  # ← pas setdefault, mais une vraie assignation

    updated = 0
    for variant in template.product_variant_ids:
        pvals = variant.product_template_attribute_value_ids
        v_ids = [pv.product_attribute_value_id.id for pv in pvals if pv.attribute_id.id == attribute.id]
        if not v_ids:
            continue
        val_id = v_ids[0]
        code = val_to_code.get(val_id)
        if not code:
            continue

        info = dimensions_by_code.get(code, {})
        label = info.get('variant_label', '').strip()

        dims_to_write = {
            'product_diameter': info.get('product_diameter', 0.0),
            'product_length': info.get('product_length', 0.0),
            'product_width': info.get('product_width', 0.0),
            'product_height': info.get('product_height', 0.0),
            'product_thickness': info.get('product_thickness', 0.0),
        }

        new_name = f"{template.name} {label}".strip()

        variant.write({
            'default_code': code,
            'name': new_name,
            **dims_to_write
        })
        updated += 1
        print(f"✅ Variante mise à jour : {variant.display_name} → {code}")

    cr.commit()
    print(f"\n✅ Import terminé avec succès ! Variantes mises à jour : {updated}")

except Exception as e:
    cr.rollback()
    print("\n❌ Erreur :", e)

finally:
    cr.close()
