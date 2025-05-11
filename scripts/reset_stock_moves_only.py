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
    print("📦 Suppression des mouvements de stock...")

    # Recherche des mouvements (tous, quel que soit l'état)
    moves = env['stock.move'].search([])
    print(f"\n🔍 {len(moves)} mouvements trouvés.")

    for move in moves:
        picking = move.picking_id
        print(f"\n⛔ Mouvement : {move.name} [{picking.name if picking else 'sans picking'}]")

        # Si picking terminé, tenter annulation
        if picking and picking.state == 'done':
            try:
                picking.action_cancel()
                print(f"   - Picking annulé : {picking.name}")
            except Exception as e:
                print(f"   ⚠️ Impossible d’annuler le picking {picking.name} → {str(e)} (on continue...)")

        # Tenter de repasser à draft
        try:
            if move.state != 'draft':
                move.write({'state': 'draft'})
                print("   - État repassé à draft.")
        except Exception as e:
            print(f"   ⚠️ Échec de passage en draft : {str(e)} (on continue...)")

        # Tenter la suppression + correction UoM si besoin
        try:
            move.unlink()
            print("   - Mouvement supprimé.")
        except Exception as e:
            if "unité de mesure" in str(e):
                try:
                    move.write({'product_uom': 29})  # Forcer ML (ID 29)
                    print("   ⚙️ UoM corrigée → ML (ID 29), tentative de suppression...")
                    move.unlink()
                    print("   - Mouvement supprimé après correction UoM.")
                except Exception as e2:
                    print(f"   ❌ Échec après correction UoM : {str(e2)}")
            else:
                print(f"   ⚠️ Impossible de supprimer le mouvement {move.name} → {str(e)}")

    cr.commit()
    print("\n✅ Tous les mouvements traités.")

except Exception as e:
    cr.rollback()
    print("\n❌ Erreur globale :", e)

finally:
    cr.close()
