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

        return round(cost_price, 4), round(sale_price, 4)

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
    return round(cost_price, 4), round(sale_price, 4)

def calculate_price_fer_plat(width, thickness, poids_total_kg, nb_barres, prix_kg, variant):
    try:
        w = safe_float(variant.product_width)
        t = safe_float(variant.product_thickness)

        if not all([w, t]):
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

def calculate_and_update_prices():
    print("\n📦 Sélection du modèle de produit (template)")
    tmpl_id = int(input("Entrez l'ID du product.template à traiter : ").strip())

    print("\n🔧 Sélection du profil :")
    profiles = {
        "1": ("Tube carré / rectangulaire", calculate_price_tube_section),
        "2": ("Fer plat", calculate_price_fer_plat),
        "3": ("Cornière (égale ou inégale)", calculate_price_corniere),
    }
    for key, (name, _) in profiles.items():
        print(f" {key}. {name}")

    profile_choice = input("Choisissez le profil à utiliser : ").strip()
    if profile_choice not in profiles:
        print("❌ Profil inconnu.")
        return

    profile_name, calc_function = profiles[profile_choice]
    print(f"\n🧲 Calcul basé sur le profil : {profile_name}")

    if profile_choice == "1":
        height = safe_float(input("Hauteur de référence (mm) : "))
        width = safe_float(input("Largeur de référence (mm) : "))
        thickness = safe_float(input("Épaisseur de référence (mm) : "))
        reference_price = safe_float(input("Prix d'achat du mètre linéaire (€) : "))
    elif profile_choice == "2":
        width = safe_float(input("Largeur (mm) : "))
        height = safe_float(input("Hauteur de référence (mm) : "))
        poids_total_kg = safe_float(input("Poids total acheté (kg) : "))
        nb_barres = int(input("Nombre de barres achetées : "))
        prix_kg = safe_float(input("Prix d'achat au kg (€) : "))
    elif profile_choice == "3":
        height = safe_float(input("Hauteur (mm) : "))
        width = safe_float(input("Largeur (mm) : "))
        thickness = safe_float(input("Épaisseur (mm) : "))
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

    for variant in variants:
        if profile_choice == "1":
            cost_price, sale_price = calc_function(height, width, thickness, reference_price, variant)
        elif profile_choice == "2":
            cost_price, sale_price = calc_function(width, width, poids_total_kg, nb_barres, prix_kg, variant)
        elif profile_choice == "3":
            cost_price, sale_price = calc_function(width, height, thickness, poids_total_kg, nb_barres, prix_kg, variant)

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
