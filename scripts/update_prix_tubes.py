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

# Fonction pour calculer le prix des tubes carrés / rectangulaires
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

# Fonction pour calculer le prix des fers plats
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

        return round(cost_price, 2), round(sale_price, 2)

    except Exception as e:
        print(f"[X] Erreur de calcul fer plat pour {variant.display_name} : {e}")
        return None, None

# Fonction pour calculer le prix des cornières
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

        return round(cost_price, 2), round(sale_price, 2)

    except Exception as e:
        print(f"[X] Erreur de calcul cornière pour {variant.display_name} : {e}")
        return None, None

# Fonction pour calculer le prix des tubes ronds
def calculate_price_tube_rond(d_ref_mm, t_ref_mm, prix_ref_m, variant):
    try:
        d = safe_float(variant.product_diameter) * 1000
        t = safe_float(variant.product_thickness) * 1000

        if not all([d, t]):
            print(f"[!] Dimensions manquantes pour {variant.display_name}")
            return None, None

        surface_ref = math.pi * d_ref_mm
        prix_mm2 = prix_ref_m / (surface_ref * t_ref_mm)

        surface_var = math.pi * d
        cost_price = prix_mm2 * surface_var * t
        sale_price = cost_price * 2.5

        return round(cost_price, 2), round(sale_price, 2)

    except Exception as e:
        print(f"[X] Erreur de calcul tube rond pour {variant.display_name} : {e}")
        return None, None

# Fonction pour lister les templates de la catégorie Métal au mètre (ID 6)
def lister_templates_metal():
    print("\n--- Produits dans la catégorie 'Métal au mètre' (ID 6) ---")
    templates = env['product.template'].search([('categ_id', '=', 6)])
    for tmpl in templates:
        print(f"ID: {tmpl.id} | Nom: {tmpl.name}")
