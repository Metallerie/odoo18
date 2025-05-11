import sys
import os

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
    # 🔍 Lister les templates dans la catégorie ID 6
    templates = env['product.template'].search([('categ_id', '=', 6)])
    if not templates:
        raise Exception("❌ Aucun product.template trouvé dans la catégorie 'Métal au mètre'.")

    print("\n📦 Produits trouvés dans la catégorie 'Métal au mètre' (ID 6) :")
    for t in templates:
        print(f" - ID: {t.id} | Nom: {t.name} | Variantes: {len(t.product_variant_ids)}")

    template_id = int(input("\n✂️ Entrez l'ID du product.template dont tu veux supprimer toutes les variantes : "))
    template = env['product.template'].browse(template_id)

    if not template.exists():
        raise Exception("❌ Ce template n'existe pas.")

    variants = template.product_variant_ids
    print(f"\n⚠️ {len(variants)} variante(s) vont être supprimées pour : {template.name}")

    confirm = input("✅ Confirme la suppression ? (oui/non) : ").strip().lower()
    if confirm != 'oui':
        print("❌ Annulé.")
    else:
        variants.unlink()
        print("🧹 Variantes supprimées avec succès.")
        cr.commit()

except Exception as e:
    cr.rollback()
    print(f"\n❌ Erreur : {e}")

finally:
    cr.close()
