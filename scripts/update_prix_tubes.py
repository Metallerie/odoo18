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

def calculate_price_corniere(width_ref, height_ref, thickness_ref, poids_total_kg, nb_barres, prix_kg, variant):
    try:
        h = safe_float(variant.product_height)
        w = safe_float(variant.product_width)

        if not all([h, w]):
            print(f"[!] Dimensions manquantes pour {variant.display_name}, ignoré.")
            return None, None, None

        poids_par_m = poids_total_kg / (nb_barres * 6.2)
        prix_par_m = poids_par_m * prix_kg

        width_ref_m = width_ref / 1000
        height_ref_m = height_ref / 1000
        thickness_ref_m = thickness_ref / 1000

        surface_ref_m2 = (width_ref_m + height_ref_m) * thickness_ref_m
        surface_var_m2 = (w + h) * thickness_ref_m

        if surface_ref_m2 == 0:
            print("[!] Surface de référence nulle pour cornière, vérifie tes valeurs.")
            return None, None, None

        ratio_surface = surface_var_m2 / surface_ref_m2
        cost_price = prix_par_m * ratio_surface
        sale_price = cost_price * 2.5

        print(f"{variant.default_code} | surface={int(surface_var_m2 * 1_000_000)} mm² | coûts={cost_price:.2f} € | vente={sale_price:.2f} €")

        return round(cost_price, 2), round(sale_price, 2), round(poids_par_m, 4)

    except Exception as e:
        print(f"[X] Erreur de calcul cornière pour {variant.display_name} : {e}")
        return None, None, None

def calculate_price_fer_plat(width_ref, height_ref, poids_total_kg, nb_barres, prix_kg, variant):
    try:
        w = safe_float(variant.product_width)
        h = safe_float(variant.product_height)

        if not all([w, h]):
            print(f"[!] Dimensions manquantes pour {variant.display_name}, ignoré.")
            return None, None, None

        poids_par_barre = poids_total_kg / nb_barres
        poids_par_m = poids_par_barre / 6.2

        width_ref_m = width_ref / 1000
        height_ref_m = height_ref / 1000
        surface_ref_m2 = width_ref_m * height_ref_m
        surface_var_m2 = w * h

        if surface_ref_m2 == 0:
            print("[!] Surface de référence nulle, vérifie tes valeurs.")
            return None, None, None

        prix_par_m_ref = poids_par_m * prix_kg
        ratio_surface = surface_var_m2 / surface_ref_m2

        cost_price = prix_par_m_ref * ratio_surface
        sale_price = cost_price * 2.5

        print(f"{variant.default_code} | surface={int(surface_var_m2 * 1_000_000)} mm² | coûts={cost_price:.2f} € | vente={sale_price:.2f} €")

        return round(cost_price, 2), round(sale_price, 2), round(poids_par_m, 4)

    except Exception as e:
        print(f"[X] Erreur de calcul fer plat pour {variant.display_name} : {e}")
        return None, None, None

def calculate_and_update_prices():
    # ... jusqu'à la boucle variants ...

    for variant in variants:
        if profile_choice == "1":
            cost_price, sale_price = calc_function(height, width, thickness, reference_price, variant)
            poids_par_m = 0.0
        elif profile_choice == "2":
            cost_price, sale_price, poids_par_m = calc_function(width_ref, height_ref, poids_total_kg, nb_barres, prix_kg, variant)
        elif profile_choice == "3":
            cost_price, sale_price, poids_par_m = calc_function(width_ref, height_ref, thickness_ref, poids_total_kg, nb_barres, prix_kg, variant)
        elif profile_choice == "4":
            cost_price, sale_price = calc_function(d_ref_mm, t_ref_mm, prix_ref_m, variant)
            poids_par_m = 0.0

        if cost_price is None:
            print(f"[!] Pas de mise à jour pour {variant.display_name}")
            continue

        prix_par_variant[variant.id] = sale_price

        variant.write({
            'standard_price': cost_price,
            'lst_price': sale_price,
            'product_kg_ml': poids_par_m
        })

        # ... reste inchangé ...

if __name__ == '__main__':
    try:
        calculate_and_update_prices()
    finally:
        cr.close()
