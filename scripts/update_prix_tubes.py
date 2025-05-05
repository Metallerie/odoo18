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

def calculate_price_corniere(width, height, thickness, poids_total_kg, nb_barres, prix_kg, variant):
    try:
        h = variant.product_height
        w = variant.product_width
        t = variant.product_thickness

        if h is None or w is None or t is None:
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

        return round(cost_price, 4), round(sale_price, 4)

    except Exception as e:
        print(f"❌ Erreur de calcul cornière pour {variant.display_name} : {e}")
        return None, None

def calculate_price_tube_section(height, width, thickness, reference_price, variant):
    h = variant.product_height
    w = variant.product_width
    t = variant.product_thickness

    if h is None or w is None or t is None:
        print(f"⚠️ Dimensions manquantes pour {variant.display_name}, ignoré.")
        return None, None

    surface_ref = (height + width) * 2
    base_unit_price = reference_price / (surface_ref * thickness)

    surface_var = (h * 1000 + w * 1000) * 2
    cost_price = base_unit_price * surface_var * (t * 1000)
    sale_price = cost_price * 2.5
    return round(cost_price, 4), round(sale_price, 4)

def calculate_price_fer_plat(width, thickness, poids_total_kg, nb_barres, prix_kg, variant):
    try:
        w = variant.product_width
        t = variant.product_thickness

        if w is None or t is None:
            print(f"⚠️ Dimensions manquantes pour {variant.display_name}, ignoré.")
            return None, None

        poids_par_m = poids_total_kg / (nb_barres * 6.2)
        prix_par_m = poids_par_m * prix_kg

        surface_ref_mm2 = width * 1000
        volume_ref_mm3 = surface_ref_mm2 * thickness

        prix_par_mm3 = prix_par_m / volume_ref_mm3

        surface_var_mm2 = w * 1000
        volume_var_mm3 = surface_var_mm2 * t

        cost_price = volume_var_mm3 * prix_par_mm3
        sale_price = cost_price * 2.5

        return round(cost_price, 4), round(sale_price, 4)
    except Exception as e:
        print(f"❌ Erreur de calcul fer plat pour {variant.display_name} : {e}")
        return None, None

# ... le reste du code est inchangé ...
