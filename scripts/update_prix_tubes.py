import sys
import os
import builtins

# --- Configuration de l'environnement Odoo ---
sys.path.append('/data/odoo/metal-odoo18-p8179')
os.environ['ODOO_RC'] = '/data/odoo/metal-odoo18-p8179/odoo18.conf'

import odoo
from odoo import api, tools, sql_db

DB = 'metal-prod-18'

tools.config.parse_config([])
odoo.service.server.load_server_wide_modules()

import odoo.netsvc as netsvc
netsvc.open = builtins.open

db = sql_db.db_connect(DB)
cr = db.cursor()
env = api.Environment(cr, 1, {})

def calculate_price_tube_carre(height, width, thickness, reference_price, variant):
    surface_ref = (height + width) * 2
    base_unit_price = reference_price / (surface_ref * thickness)

    h = variant.product_height
    w = variant.product_width
    t = variant.product_thickness

    if not all([h, w, t]):
        print(f"⚠️ Dimensions manquantes pour {variant.display_name}, ignoré.")
        return None, None

    surface_var = (h * 1000 + w * 1000) * 2
    cost_price = base_unit_price * surface_var * (t * 1000)
    sale_price = cost_price * 2.5
    return cost_price, sale_price

def calculate_and_update_prices():
    print("\n📦 Sélection du modèle de produit (template)")
    tmpl_id = int(input("Entrez l'ID du product.template à traiter : ").strip())

    print("\n🔧 Sélection du profil :")
    profiles = {
        "1": ("Tube carré", calculate_price_tube_carre),
        # Ajouts futurs : "2": ("Tube rectangulaire", calculate_price_tube_rectangulaire), etc.
    }
    for key, (name, _) in profiles.items():
        print(f" {key}. {name}")

    profile_choice = input("Choisissez le profil à utiliser : ").strip()
    if profile_choice not in profiles:
        print("❌ Profil inconnu.")
        return

    profile_name, calc_function = profiles[profile_choice]

    print(f"\n🧮 Calcul basé sur le profil : {profile_name}")
    height = float(input("Hauteur de référence (mm) : "))
    width = float(input("Largeur de référence (mm) : "))
    thickness = float(input("Épaisseur de référence (mm) : "))
    reference_price = float(input("Prix d'achat du mètre linéaire (€) : "))

    pricelist = env['product.pricelist'].search([('name', '=', 'Métal au mètre')], limit=1)
    if not pricelist:
        pricelist = env['product.pricelist'].create({
            'name': 'Métal au mètre',
            'currency_id': env.ref('base.EUR').id,
        })

    variants = env['product.product'].search([('product_tmpl_id', '=', tmpl_id)])

    for variant in variants:
        cost_price, sale_price = calc_function(height, width, thickness, reference_price, variant)

        if cost_price is None:
            continue

        variant.write({'standard_price': cost_price})

        pricelist_item = env['product.pricelist.item'].search([
            ('pricelist_id', '=', pricelist.id),
            ('product_id', '=', variant.id)
        ], limit=1)

        if pricelist_item:
            pricelist_item.write({'fixed_price': sale_price})
        else:
            env['product.pricelist.item'].create({
                'pricelist_id': pricelist.id,
                'applied_on': '0_product_variant',
                'product_id': variant.id,
                'fixed_price': sale_price,
            })

        if variant.product_thickness in (0.004, 0.005):
            variant.write({'active': False})
            print(f"{variant.display_name}: désactivé (épaisseur spéciale)")
        else:
            variant.write({'active': True})
            print(f"{variant.display_name}: cout={cost_price:.4f} €, vente={sale_price:.4f} €")

    env.cr.commit()

if __name__ == '__main__':
    try:
        calculate_and_update_prices()
    finally:
        cr.close()
