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

def calculate_price_corniere(width, height, thickness, poids_total_kg, nb_barres, prix_kg, variant):
    try:
        h = safe_float(variant.product_height)
        w = safe_float(variant.product_width)
        t = safe_float(variant.product_thickness)

        if not all([h, w, t]):
            print(f"⚠️ Dimensions manquantes pour {variant.display_name}, ignoré.")
            return None, None

        poids_par_m = poids_total_kg / (nb_barres * 6.2)
        prix_par_m = poids_par_m * prix_kg

        surface_ref_mm2 = (width + height) * 1000
        volume_ref_mm3 = surface_ref_mm2 * thickness

        prix_par_mm3 = prix_par_m / volume_ref_mm3

        surface_var_mm2 = (w + h) * 1000
        volume_var_mm3 = surface_var_mm2 * t

        cost_price = volume_var_mm3 * prix_par_mm3
        sale_price = cost_price * 2.5

        return round(cost_price, 2), round(sale_price, 2)

    except Exception as e:
        print(f"❌ Erreur de calcul cornière pour {variant.display_name} : {e}")
        return None, None

def calculate_price_tube_section(height, width, thickness, reference_price, variant):
    surface_ref = (height + width) * 2
    base_unit_price = reference_price / (surface_ref * thickness)

    h = safe_float(variant.product_height)
    w = safe_float(variant.product_width)
    t = safe_float(variant.product_thickness)

    if not all([h, w, t]):
        print(f"⚠️ Dimensions manquantes pour {variant.display_name}, ignoré.")
        return None, None

    surface_var = (h * 1000 + w * 1000) * 2
    cost_price = base_unit_price * surface_var * (t * 1000)
    sale_price = cost_price * 2.5
    return round(cost_price, 2), round(sale_price, 2)

def calculate_price_fer_plat(width, height, poids_total_kg, nb_barres, prix_kg, variant):
    try:
        w = safe_float(variant.product_width)
        h = safe_float(variant.product_height)

        if not all([w, h]):
            print(f"⚠️ Dimensions manquantes pour {variant.display_name}, ignoré.")
            return None, None

        longueur_m = nb_barres * 6.2
        poids_total_mg = poids_total_kg * 1_000_000
        poids_par_m_mg = poids_total_mg / longueur_m
        prix_par_m = poids_par_m_mg * (prix_kg / 1_000_000)

        volume_var_mm3 = w * h * 1000  # longueur = 1 mètre = 1000 mm
        masse_var_mg = volume_var_mm3 * 7.85  # densité acier = 7.85 mg/mm3

        if poids_par_m_mg == 0:
            print(f"🚨 poids_par_m_mg est nul pour {variant.display_name}")
            return None, None

        cost_price = (masse_var_mg / poids_par_m_mg) * prix_par_m
        sale_price = cost_price * 2.5

        print(f"🔍 {variant.default_code} | W={w} H={h} | volume_var_mm3={volume_var_mm3:.0f} | masse_mg={masse_var_mg:.0f} | poids_par_m_mg={poids_par_m_mg:.0f} | prix_par_m={prix_par_m:.4f} | cost={cost_price:.4f} | vente={sale_price:.4f}")

        return round(cost_price, 4), round(sale_price, 4)

    except Exception as e:
        print(f"❌ Erreur de calcul fer plat pour {variant.display_name} : {e}")
        return None, None

# ... Le reste du code ne change pas ...
