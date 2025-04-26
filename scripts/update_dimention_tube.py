import sys
import os
import re

sys.path.append('/data/odoo/metal-odoo18-p8179')
os.environ['ODOO_RC'] = '/data/odoo/metal-odoo18-p8179/odoo18.conf'

import odoo
from odoo import api, tools, sql_db

DB = 'metal-prod-18'
TEMPLATE_ID = 7  # ID du template "Tube soudés carrés"

# Initialisation
tools.config.parse_config()
odoo.service.server.load_server_wide_modules()
db = sql_db.db_connect(DB)
cr = db.cursor()
env = api.Environment(cr, 1, {})  # Superadmin

def mm_to_m(valeur_mm):
    return float(valeur_mm.replace('mm', '').replace(',', '.').strip()) / 1000

try:
    template = env['product.template'].browse(TEMPLATE_ID)
    variants = env['product.product'].search([('product_tmpl_id', '=', template.id)])

    for variant in variants:
        match = re.search(r"(\d+)[xX](\d+).*x *(\d+[,\.]?\d*)", variant.name)
        if match:
            largeur_mm = match.group(1)
            hauteur_mm = match.group(2)
            epaisseur_mm = match.group(3)

            largeur_m = mm_to_m(largeur_mm)
            hauteur_m = mm_to_m(hauteur_mm)
            epaisseur_m = mm_to_m(epaisseur_mm)

            # Mise à jour des dimensions
            variant.width = largeur_m
            variant.height = hauteur_m
            variant.thickness = epaisseur_m
            variant.length = 1.0  # 1 mètre car UoM ML

            # UoM dimensionnelle forcée à ML
            if variant.dimension_uom_id:
                dimension_uom = env['uom.uom'].search([('name', '=', 'ML')], limit=1)
                if dimension_uom:
                    variant.dimension_uom_id = dimension_uom.id

            print(f"🔁 {variant.name} → Largeur: {largeur_m:.3f} m, Hauteur: {hauteur_m:.3f} m, Épaisseur: {epaisseur_m:.3f} m")
        else:
            print(f"⚠️ Format non reconnu pour : {variant.name}")

    cr.commit()
    print("\n✅ Dimensions mises à jour pour tous les tubes carrés.")

except Exception as e:
    cr.rollback()
    print("\n❌ Erreur :", e)

finally:
    cr.close()
