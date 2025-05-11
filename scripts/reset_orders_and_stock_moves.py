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
    print("🔄 Démarrage de la remise à zéro des commandes et mouvements de stock...")

    # === 🔁 RAZ des commandes clients ===
    orders = env['sale.order'].search([('state', '=', 'sale')])
    print(f"\n🧾 {len(orders)} commandes confirmées à traiter...")

    for order in orders:
        print(f"\n⛔ Annulation de la commande : {order.name}")

        # Annulation des livraisons associées
        pickings = order.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'])
        for picking in pickings:
            picking.action_cancel()
            print(f"   - Livraison annulée : {picking.name}")

        order.action_cancel()
        order.write({'state': 'draft'})
        print("   - Repassée en brouillon.")

        order.unlink()
        print("   - Supprimée.")

    # === 📦 RAZ des mouvements de stock ===
    moves = env['stock.move'].search([('state', '=', 'done')])
    print(f"\n📦 {len(moves)} mouvements de stock terminés à traiter...")

    for move in moves:
        picking = move.picking_id
        print(f"\n⛔ Mouvement : {move.name} [{picking.name if picking else 'sans picking'}]")

        # Annulation du picking si nécessaire
        if picking and picking.state == 'done':
            picking.button_cancel()
            print(f"   - Picking annulé : {picking.name}")

        # Repasse le move en brouillon si possible
        if move.state != 'draft':
            move.write({'state': 'draft'})
            print("   - État repassé à draft.")

        move.unlink()
        print("   - Mouvement supprimé.")

    cr.commit()
    print("\n✅ Remise à zéro terminée avec succès !")

except Exception as e:
    cr.rollback()
    print("\n❌ Erreur :", e)

finally:
    cr.close()
