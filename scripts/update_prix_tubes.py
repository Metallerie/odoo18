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
            print(f"\u26a0\ufe0f Dimensions manquantes pour {variant.display_name}, ignoré.")
            return None, None

        poids_par_m = poids_total_kg / (nb_barres * 6.2)
        prix_par_m = poids_par_m * prix_kg

        width_ref_m = width_ref / 1000
        height_ref_m = height_ref / 1000
        thickness_ref_m = thickness_ref / 1000

        surface_ref_m2 = (width_ref_m + height_ref_m) * thickness_ref_m
        surface_var_m2 = (w + h) * thickness_ref_m  # Utilise la même épaisseur de réf

        if surface_ref_m2 == 0:
            print(f"🚨 Surface de référence nulle pour cornière, vérifie tes valeurs.")
            return None, None

        ratio_surface = surface_var_m2 / surface_ref_m2
        cost_price = prix_par_m * ratio_surface
        sale_price = cost_price * 2.5

        print(f"🧲 {variant.default_code} | surface={int(surface_var_m2 * 1_000_000)} mm² | coûts={cost_price:.2f} € | vente={sale_price:.2f} €")

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

def calculate_price_fer_plat(width_ref, height_ref, poids_kg_par_barre, prix_kg, variant):
    try:
        w = safe_float(variant.product_width)
        h = safe_float(variant.product_height)

        if not all([w, h]):
            print(f"⚠️ Dimensions manquantes pour {variant.display_name}, ignoré.")
            return None, None

        # Convertir la référence en mètres
        width_ref_m = width_ref / 1000
        height_ref_m = height_ref / 1000

        surface_ref_m2 = width_ref_m * height_ref_m
        surface_var_m2 = w * h

        if surface_ref_m2 == 0:
            print(f"🚨 Surface de référence nulle, vérifie tes valeurs.")
            return None, None

        poids_par_m_ref = poids_kg_par_barre / 6.2
        prix_par_m_ref = poids_par_m_ref * prix_kg

        ratio_surface = surface_var_m2 / surface_ref_m2
        cost_price = prix_par_m_ref * ratio_surface
        sale_price = cost_price * 2.5

        print(f"🧲 {variant.default_code} | surface={int(surface_var_m2 * 1_000_000)} mm² | coûts={cost_price:.2f} € | vente={sale_price:.2f} €")

        return round(cost_price, 2), round(sale_price, 2)

    except Exception as e:
        print(f"❌ Erreur de calcul fer plat pour {variant.display_name} : {e}")
        return None, None

# Le reste du script est inchangé, centré sur calculate_and_update_prices()
# Il utilisera ces fonctions corrigées automatiquement selon le profil choisi

if __name__ == '__main__':
    try:
        calculate_and_update_prices()
    finally:
        cr.close()
