import sys
import os
import builtins
import math

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

# Fonction utilitaire pour accepter les valeurs nulles ou vides
def safe_float(val):
    try:
        return float(str(val).strip()) if str(val).strip() else 0.0
    except Exception:
        return 0.0

# Fonction pour lister les templates dans la catégorie Métal au mètre (ID 6)
def lister_templates_metal():
    print("\n--- Produits dans la catégorie 'Métal au mètre' (ID 6) ---")
    templates = env['product.template'].search([('categ_id', '=', 6)])
    for tmpl in templates:
        print(f"ID: {tmpl.id} | Nom: {tmpl.name}")

# Fonction principale de mise à jour des prix
def calculate_and_update_prices():
    lister_templates_metal()

    print("\n--- Sélection du modèle de produit (template) ---")
    tmpl_id = int(input("Entrez l'ID du product.template à traiter : ").strip())

    print("\n--- Sélection du profil : ---")
    profiles = {
        "1": ("Tube carré / rectangulaire", calculate_price_tube_section),
        "2": ("Fer plat", calculate_price_fer_plat),
        "3": ("Cornière (égale ou inégale)", calculate_price_corniere),
        "4": ("Tube rond", calculate_price_tube_rond),
    }
    for key, (name, _) in profiles.items():
        print(f" {key}. {name}")

    profile_choice = input("Choisissez le profil à utiliser : ").strip()
    if profile_choice not in profiles:
        print("[X] Profil inconnu.")
        return

    profile_name, calc_function = profiles[profile_choice]
    print(f"\n--- Calcul basé sur le profil : {profile_name} ---")

    if profile_choice == "1":
        height = safe_float(input("Hauteur de référence (mm) : "))
        width = safe_float(input("Largeur de référence (mm) : "))
        thickness = safe_float(input("Épaisseur de référence (mm) : "))
        reference_price = safe_float(input("Prix d'achat du mètre linéaire (€) : "))
    elif profile_choice == "2":
        width_ref = safe_float(input("Largeur de référence (mm) : "))
        height_ref = safe_float(input("Épaisseur de référence (mm) : "))
        poids_total_kg = safe_float(input("Poids total de la commande (kg) : "))
        nb_barres = int(input("Nombre de barres achetées : "))
        prix_kg = safe_float(input("Prix d'achat au kg (€) : "))
        poids_par_barre = poids_total_kg / nb_barres
    elif profile_choice == "3":
        width_ref = safe_float(input("Largeur de référence (mm) : "))
        height_ref = safe_float(input("Hauteur de référence (mm) : "))
        thickness_ref = safe_float(input("Épaisseur de référence (mm) : "))
        poids_total_kg = safe_float(input("Poids total acheté (kg) : "))
        nb_barres = int(input("Nombre de barres achetées : "))
        prix_kg = safe_float(input("Prix d'achat au kg (€) : "))
    elif profile_choice == "4":
        d_ref = safe_float(input("Diamètre de référence (mm) : "))
        t_ref = safe_float(input("Épaisseur de référence (mm) : "))
        prix_ref_m = safe_float(input("Prix d'achat du mètre linéaire (€) : "))

    pricelist = env['product.pricelist'].search([('name', '=', 'Métal au mètre')], limit=1)
    if not pricelist:
        pricelist = env['product.pricelist'].create({
            'name': 'Métal au mètre',
            'currency_id': env.ref('base.EUR').id,
        })

    variants = env['product.product'].search([('product_tmpl_id', '=', tmpl_id)])
    total_updated = 0
    min_sale_price = None
    prix_par_variant = {}

    for variant in variants:
        if profile_choice == "1":
            cost_price, sale_price = calc_function(height, width, thickness, reference_price, variant)
        elif profile_choice == "2":
            cost_price, sale_price = calc_function(width_ref, height_ref, poids_par_barre, prix_kg, variant)
        elif profile_choice == "3":
            cost_price, sale_price = calc_function(width_ref, height_ref, thickness_ref, poids_total_kg, nb_barres, prix_kg, variant)
        elif profile_choice == "4":
            cost_price, sale_price = calc_function(d_ref, t_ref, prix_ref_m, variant)

        if cost_price is None:
            print(f"[!] Pas de mise à jour pour {variant.display_name}")
            continue

        prix_par_variant[variant.id] = sale_price

        variant.write({
            'standard_price': cost_price,
            'lst_price': sale_price
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

        if min_sale_price is None or sale_price < min_sale_price:
            min_sale_price = sale_price

        print(f"[{variant.id}] {variant.display_name}: standard={cost_price:.2f} €, vente={sale_price:.2f} €")
        total_updated += 1

    print(f"\n--- Total variantes mises à jour : {total_updated} ---")
    print(f"--- Prix le plus bas attribué aux variantes : {min_sale_price:.2f} € ---")
    if min_sale_price is not None:
        for variant in variants:
            variant.lst_price = min_sale_price
            print(f"[{variant.default_code}] ✅ lst_price ajusté à {min_sale_price:.2f} € (prix le plus bas)")

    env.cr.commit()

if __name__ == '__main__':
    try:
        calculate_and_update_prices()
    finally:
        cr.close()
