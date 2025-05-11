import sys
import os

# 🔧 Config Odoo
sys.path.append('/data/odoo/metal-odoo18-p8179')
os.environ['ODOO_RC'] = '/data/odoo/metal-odoo18-p8179/odoo18.conf'

import odoo
from odoo import api, tools, sql_db

# ⚙️ Initialisation
tools.config.parse_config()
odoo.service.server.load_server_wide_modules()
db = sql_db.db_connect('metal-prod-18')
cr = db.cursor()
env = api.Environment(cr, 1, {})

try:
    print("📦 Suppression des mouvements de stock terminés...")

    # Recherche des mouvements de stock en 'done'
    moves = env['stock.move'].search([('state', '=', 'done')])
    print(f"\n🔍 {len(moves)} mouvements trouvés.")

    for move in moves:
        picking = move.picking_id
        print(f"\n⛔ Mouvement : {move.name} [{picking.name if picking else 'sans picking'}]")

        # Annuler le picking si encore actif
        if picking and picking.state == 'done':
            picking.button_cancel()
            print(f"   - Picking annulé : {picking.name}")

        # Repasser le move en draft
        if move.state != 'draft':
            move.write({'state': 'draft'})
            print("   - État repassé à draft.")

        move.unlink()
        print("   - Mouvement supprimé.")

    cr.commit()
    print("\n✅ Tous les mouvements de stock terminés ont été supprimés.")

except Exception as e:
    cr.rollback()
    print("\n❌ Erreur :", e)

finally:
    cr.close()
