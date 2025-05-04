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

def calculate_price_tube_section(height, width, thickness, reference_price, variant):
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
    return round(cost_price, 4), round(sale_price, 4)

def calculate_price_fer_plat(width, thickness, poids_total_kg, nb_barres, prix_kg, variant):
    try:
        longueur_barre = 6.2  # mètres
        poids_par_barre = poids_total_kg / nb_barres
        poids_par_m = poids_par_barre / longueur_barre
        prix_metre = poids_par_m * prix_kg

        base_unit_price = prix_metre / (width * thickness)

        w = variant.product_width
        t = variant.product_thickness

        if not all([w, t]):
            print(f"⚠️ Dimensions manquantes pour {variant.display_name}, ignoré.")
            return None, None

        cost_price = base_unit_price * (w * 1000) * (t * 1000)
        sale_price = cost_price * 2.5
        return round(cost_price, 4), round(sale_price, 4)
    except Exception as e:
        print(f"❌ Erreur de calcul fer plat pour {variant.display_name} : {e}")
        return None, None

def calculate_and_update_prices():
    print("\n📦 Sélection du modèle de produit (template)")
    tmpl_id = int(input("Entrez l'ID du product.template à traiter : ").strip())

    print("\n🔧 Sélection du profil :")
    profiles = {
        "1": ("Tube carré / rectangulaire", calculate_price_tube_section),
        "2": ("Fer plat", calculate_price_fer_plat),
    }
    for key, (name, _) in profiles.items():
        print(f" {key}. {name}")

    profile_choice = input("Choisissez le profil à utiliser : ").strip()
    if profile_choice not in profiles:
        print("❌ Profil inconnu.")
        return

    profile_name, calc_function = profiles[profile_choice]
    print(f"\n🧮 Calcul basé sur le profil : {profile_name}")

    if profile_choice == "1":
        height = float(input("Hauteur de référence (mm) : "))
        width = float(input("Largeur de référence (mm) : "))
        thickness = float(input("Épaisseur de référence (mm) : "))
        reference_price = float(input("Prix d'achat du mètre linéaire (€) : "))
    elif profile_choice == "2":
        width = float(input("Largeur du fer plat (mm) : "))
        thickness = float(input("Épaisseur du fer plat (mm) : "))
        poids_total_kg = float(input("Poids total acheté (kg) : "))
        nb_barres = int(input("Nombre de barres achetées : "))
        prix_kg = float(input("Prix d'achat au kg (€) : "))

    pricelist = env['product.pricelist'].search([('name', '=', 'Métal au mètre')], limit=1)
    if not pricelist:
        pricelist = env['product.pricelist'].create({
            'name': 'Métal au mètre',
            'currency_id': env.ref('base.EUR').id,
        })

    variants = env['product.product'].search([('product_tmpl_id', '=', tmpl_id)])

    for variant in variants:
        if profile_choice == "1":
            cost_price, sale_price = calc_function(height, width, thickness, reference_price, variant)
        elif profile_choice == "2":
            cost_price, sale_price = calc_function(width, thickness, poids_total_kg, nb_barres, prix_kg, variant)

        if cost_price is None:
            continue

        variant.write({
            'standard_price': cost_price,
            'lst_price': sale_price,
        })

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
            print(f"{variant.display_name}: standard={cost_price:.4f} €, vente={sale_price:.4f} €")

    env.cr.commit()

if __name__ == '__main__':
    try:
        calculate_and_update_prices()
    finally:
        cr.close()
