import sys
import os
import re

sys.path.append('/data/odoo/metal-odoo18-p8179')
os.environ['ODOO_RC'] = '/data/odoo/metal-odoo18-p8179/odoo18.conf'

import odoo
from odoo import api, tools, sql_db

DB = 'metal-prod-18-clone'
TEMPLATE_ID = 7  # ID du template "Tube soudés carrés"

# Initialisation
tools.config.parse_config()
odoo.service.server.load_server_wide_modules()
db = sql_db.db_connect(DB)
cr = db.cursor()
env = api.Environment(cr, 1, {})  # Superadmin

try:
    template = env['product.template'].browse(TEMPLATE_ID)
    variants = env['product.product'].search([('product_tmpl_id', '=', template.id)])

    for variant in variants:
        match = re.search(r"(\d+)[xX](\d+).*x *(\d+[\.,]?\d*)", variant.name)
        if match:
            largeur = float(match.group(1))
            hauteur = float(match.group(2))
            epaisseur = float(match.group(3).replace(',', '.'))

            surface_unit_mm2 = (largeur * 4) * 1000
            coef = 0.000015  # Nouveau coefficient stable validé
            prix_achat = surface_unit_mm2 * coef
            prix_vente_ht = prix_achat * 2.5
            prix_vente_ttc = round(prix_vente_ht * 1.2, 2)

            variant.standard_price = round(prix_achat, 3)
            variant.list_price = prix_vente_ttc
            print(f"🔁 {variant.name} → Achat: {prix_achat:.3f} €, Vente TTC: {prix_vente_ttc:.2f} €")
        else:
            print(f"⚠️ Format non reconnu pour : {variant.name}")

    cr.commit()
    print("\n✅ Prix mis à jour pour tous les tubes carrés.")

except Exception as e:
    cr.rollback()
    print("\n❌ Erreur :", e)

finally:
    cr.close()
