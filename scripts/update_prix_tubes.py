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

# Fonction utilitaire pour accepter les valeurs nulles ou vides
def safe_float(val):
    try:
        return float(str(val).strip()) if str(val).strip() else 0.0
    except Exception:
        return 0.0

def calculate_price_corniere(width_ref, height_ref, thickness_ref, poids_total_kg, nb_barres, prix_kg, variant):
    try:
        h = safe_float(variant.product_height)
        w = safe_float(variant.product_width)

        if not all([h, w]):
            print(f"[!] Dimensions manquantes pour {variant.display_name}, ignoré.")
            return None, None

        poids_par_m = poids_total_kg / (nb_barres * 6.2)
        prix_par_m = poids_par_m * prix_kg

        width_ref_m = width_ref / 1000
        height_ref_m = height_ref / 1000
        thickness_ref_m = thickness_ref / 1000

        surface_ref_m2 = (width_ref_m + height_ref_m) * thickness_ref_m
        surface_var_m2 = (w + h) * thickness_ref_m

        if surface_ref_m2 == 0:
            print("[!] Surface de référence nulle pour cornière, vérifie tes valeurs.")
            return None, None

        ratio_surface = surface_var_m2 / surface_ref_m2
        cost_price = prix_par_m * ratio_surface
        sale_price = cost_price * 2.5

        print(f"{variant.default_code} | surface={int(surface_var_m2 * 1_000_000)} mm² | coûts={cost_price:.2f} € | vente={sale_price:.2f} €")

        return round(cost_price, 2), round(sale_price, 2)

    except Exception as e:
        print(f"[X] Erreur de calcul cornière pour {variant.display_name} : {e}")
        return None, None

def calculate_price_tube_section(height, width, thickness, reference_price, variant):
    surface_ref = (height + width) * 2
    base_unit_price = reference_price / (surface_ref * thickness)

    h = safe_float(variant.product_height)
    w = safe_float(variant.product_width)
    t = safe_float(variant.product_thickness)

    if not all([h, w, t]):
        print(f"[!] Dimensions manquantes pour {variant.display_name}, ignoré.")
        return None, None

    surface_var = (h * 1000 + w * 1000) * 2
    cost_price = base_unit_price * surface_var * (t * 1000)
    sale_price = cost_price * 2.5
    return round(cost_price, 2), round(sale_price, 2)

def calculate_price_fer_plat(width_ref, height_ref, poids_kg_par_barre, prix_kg, variant):
    try:
        w = safe_float(variant.product_width)
        h = safe_float(variant.product_height)

        if not all([w, h]):
            print(f"[!] Dimensions manquantes pour {variant.display_name}, ignoré.")
            return None, None

        width_ref_m = width_ref / 1000
        height_ref_m = height_ref / 1000

        surface_ref_m2 = width_ref_m * height_ref_m
        surface_var_m2 = w * h

        if surface_ref_m2 == 0:
            print("[!] Surface de référence nulle, vérifie tes valeurs.")
            return None, None

        poids_par_m_ref = poids_kg_par_barre / 6.2
        prix_par_m_ref = poids_par_m_ref * prix_kg

        ratio_surface = surface_var_m2 / surface_ref_m2
        cost_price = prix_par_m_ref * ratio_surface
        sale_price = cost_price * 2.5

        print(f"{variant.default_code} | surface={int(surface_var_m2 * 1_000_000)} mm² | coûts={cost_price:.2f} € | vente={sale_price:.2f} €")

        return round(cost_price, 2), round(sale_price, 2)

    except Exception as e:
        print(f"[X] Erreur de calcul fer plat pour {variant.display_name} : {e}")
        return None, None

def calculate_and_update_prices():
    print("\n--- Sélection du modèle de produit (template) ---")
    tmpl_id = int(input("Entrez l'ID du product.template à traiter : ").strip())

    print("\n--- Sélection du profil : ---")
    profiles = {
        "1": ("Tube carré / rectangulaire", calculate_price_tube_section),
        "2": ("Fer plat", calculate_price_fer_plat),
        "3": ("Cornière (égale ou inégale)", calculate_price_corniere),
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

    pricelist = env['product.pricelist'].search([('name', '=', 'Métal au mètre')], limit=1)
    if not pricelist:
        pricelist = env['product.pricelist'].create({
            'name': 'Métal au mètre',
            'currency_id': env.ref('base.EUR').id,
        })

    variants = env['product.product'].search([('product_tmpl_id', '=', tmpl_id)])
    template = env['product.template'].browse(tmpl_id)
    min_sale_price = None
    total_updated = 0

    for variant in variants:
        if profile_choice == "1":
            cost_price, sale_price = calc_function(height, width, thickness, reference_price, variant)
        elif profile_choice == "2":
            cost_price, sale_price = calc_function(width_ref, height_ref, poids_par_barre, prix_kg, variant)
        elif profile_choice == "3":
            cost_price, sale_price = calc_function(width_ref, height_ref, thickness_ref, poids_total_kg, nb_barres, prix_kg, variant)

        if cost_price is None:
            print(f"[!] Pas de mise à jour pour {variant.display_name}")
            continue

        variant.write({
            'standard_price': cost_price
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

        print(f"{variant.display_name}: standard={cost_price:.2f} €, vente={sale_price:.2f} €")
        total_updated += 1

    if min_sale_price is not None:
        template.write({'lst_price': min_sale_price})

    print(f"\n--- Total variantes mises à jour : {total_updated} ---")
    env.cr.commit()

if __name__ == '__main__':
    try:
        calculate_and_update_prices()
    finally:
        cr.close()
