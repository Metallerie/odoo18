import sys
import os
import requests

sys.path.append('/data/odoo/metal-odoo18-p8179')
os.environ['ODOO_RC'] = '/data/odoo/metal-odoo18-p8179/odoo18.conf'

import odoo
from odoo import api, tools, sql_db

DB = 'metal-prod-18'  # 🧠 adapte si besoin

tools.config.parse_config()
odoo.service.server.load_server_wide_modules()

db = sql_db.db_connect(DB)
cr = db.cursor()
env = api.Environment(cr, 1, {})  # Superadmin

try:
    # 🧹 Étape 1 : suppression de toutes les catégories existantes
    count = env['product.google.category'].search_count([])
    env['product.google.category'].search([]).unlink()
    print(f"🧹 {count} catégories supprimées.")

    # 🌐 Étape 2 : téléchargement du fichier Google
    url = "https://www.google.com/basepages/producttype/taxonomy-with-ids.fr-FR.txt"
    response = requests.get(url)

    if response.status_code != 200:
        raise Exception(f"Erreur téléchargement : {response.status_code}")

    raw = response.content.decode('utf-8', errors='replace')  # ← on reste en utf-8 ici
    lines = raw.strip().split('\n')

    import_count = 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or ' - ' not in line:
            continue

        category_id, name = line.split(' - ', 1)
        name = name.strip()
        code = category_id.strip()

        env['product.google.category'].create({
            'name': name,
            'code': code,
        })
        import_count += 1

    print(f"📦 {import_count} catégories importées.")

    # 🛠️ Étape 3 : correction des caractères mal encodés
    fix_count = 0
    for cat in env['product.google.category'].search([]):
        if 'Ã' in cat.name or 'Â' in cat.name or '�' in cat.name:
            try:
                fixed = cat.name.encode('latin1', errors='ignore').decode('utf-8', errors='replace')
                if cat.name != fixed:
                    cat.name = fixed
                    fix_count += 1
                    print(f"🛠️ Corrigé : {fixed}")
            except Exception as e:
                print(f"⚠️ Erreur sur '{cat.name}': {e}")

    print(f"✅ {fix_count} noms corrigés après import.")

    cr.commit()

except Exception as e:
    cr.rollback()
    print("❌ Erreur globale :", e)

finally:
    cr.close()
