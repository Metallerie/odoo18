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
    print("🧾 Suppression des commandes POS et paiements en espèces...")

    # 🔍 Recherche des commandes POS
    pos_orders = env['pos.order'].search([])
    print(f"\n🔎 {len(pos_orders)} commandes POS trouvées.")

    for order in pos_orders:
        print(f"\n⛔ Commande POS : {order.name} | État : {order.state}")

        # Annuler les pickings liés (livraisons)
        pickings = order.picking_ids.filtered(lambda p: p.state not in ['cancel', 'done'])
        for picking in pickings:
            try:
                picking.action_cancel()
                print(f"   - Picking annulé : {picking.name}")
            except Exception as e:
                print(f"   ⚠️ Échec d'annulation picking : {str(e)}")

        # Supprimer les paiements en espèces uniquement
        cash_payments = order.statement_ids.filtered(lambda s: s.journal_id.name.lower() in ['cash', 'espèces', 'especes'])
        for payment in cash_payments:
            try:
                payment.unlink()
                print(f"   - Paiement espèce supprimé (journal : {payment.journal_id.name})")
            except Exception as e:
                print(f"   ⚠️ Paiement non supprimé → {str(e)}")

        # Annuler et supprimer la commande POS
        try:
            if order.state not in ['draft', 'cancel']:
                order.action_pos_order_cancel()
                print("   - Commande annulée.")
            order.unlink()
            print("   - Commande supprimée.")
        except Exception as e:
            print(f"   ⚠️ Erreur suppression commande POS : {str(e)}")

    cr.commit()
    print("\n✅ Toutes les commandes POS ont été traitées.")

except Exception as e:
    cr.rollback()
    print("\n❌ Erreur globale :", e)

finally:
    cr.close()
