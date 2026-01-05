#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import builtins
import math

# --- Configuration de l'environnement Odoo ---
ODOO_PATH = '/data/odoo/metal-odoo18-p8179'
ODOO_RC = '/data/odoo/metal-odoo18-p8179/odoo18.conf'
DB = 'metal-prod-18'

sys.path.append(ODOO_PATH)
os.environ['ODOO_RC'] = ODOO_RC

import odoo
from odoo import api, tools, sql_db

tools.config.parse_config([])
odoo.service.server.load_server_wide_modules()

import odoo.netsvc as netsvc
netsvc.open = builtins.open

db = sql_db.db_connect(DB)
cr = db.cursor()
env = api.Environment(cr, 1, {})

# -----------------------------
# Helpers
# -----------------------------
def safe_float(val):
    try:
        s = str(val).strip()
        return float(s) if s else 0.0
    except Exception:
        return 0.0

def has_field(model, field_name: str) -> bool:
    return field_name in model._fields

# -----------------------------
# Calculs profils existants
# -----------------------------
def calculate_price_corniere(width_ref, height_ref, thickness_ref, poids_total_kg, nb_barres, prix_kg, variant):
    try:
        h = safe_float(getattr(variant, 'product_height', 0.0))
        w = safe_float(getattr(variant, 'product_width', 0.0))

        if not all([h, w]):
            print(f"[!] Dimensions manquantes pour {variant.display_name}, ignoré.")
            return None, None, None

        # ref: 6.2 m / barre
        poids_par_m_ref = poids_total_kg / (nb_barres * 6.2)
        prix_par_m = poids_par_m_ref * prix_kg

        width_ref_m = width_ref / 1000
        height_ref_m = height_ref / 1000
        thickness_ref_m = thickness_ref / 1000

        surface_ref_m2 = (width_ref_m + height_ref_m) * thickness_ref_m
        surface_var_m2 = (w + h) * thickness_ref_m  # épaisseur ref = même base

        if surface_ref_m2 == 0:
            print("[!] Surface de référence nulle pour cornière, vérifie tes valeurs.")
            return None, None, None

        ratio_surface = surface_var_m2 / surface_ref_m2
        cost_price = prix_par_m * ratio_surface
        sale_price = cost_price * 2.5
        poids_par_m = poids_par_m_ref * ratio_surface

        print(f"{variant.default_code} | surface={int(surface_var_m2 * 1_000_000)} mm² | coût={cost_price:.2f} € | vente={sale_price:.2f} €")
        return round(cost_price, 2), round(sale_price, 2), round(poids_par_m, 3)

    except Exception as e:
        print(f"[X] Erreur de calcul cornière pour {variant.display_name} : {e}")
        return None, None, None

def calculate_price_tube_section(height, width, thickness, reference_price_m, variant):
    """
    Tube carré/rectangulaire, prix ref au mètre linéaire.
    height/width/thickness en mm (référence)
    reference_price_m en € / m (achat)
    """
    try:
        surface_ref = (height + width) * 2
        base_unit_price = reference_price_m / (surface_ref * thickness)

        h = safe_float(getattr(variant, 'product_height', 0.0))
        w = safe_float(getattr(variant, 'product_width', 0.0))
        t = safe_float(getattr(variant, 'product_thickness', 0.0))

        if not all([h, w, t]):
            print(f"[!] Dimensions manquantes pour {variant.display_name}, ignoré.")
            return None, None

        surface_var = (h * 1000 + w * 1000) * 2
        cost_price = base_unit_price * surface_var * (t * 1000)
        sale_price = cost_price * 2.5
        return round(cost_price, 2), round(sale_price, 2)

    except Exception as e:
        print(f"[X] Erreur de calcul tube section pour {variant.display_name} : {e}")
        return None, None

def calculate_price_fer_plat(width_ref, height_ref, poids_total_kg, nb_barres, prix_kg, variant):
    try:
        w = safe_float(getattr(variant, 'product_width', 0.0))
        h = safe_float(getattr(variant, 'product_height', 0.0))

        if not all([w, h]):
            print(f"[!] Dimensions manquantes pour {variant.display_name}, ignoré.")
            return None, None, None

        width_ref_m = width_ref / 1000
        height_ref_m = height_ref / 1000

        surface_ref_m2 = width_ref_m * height_ref_m
        surface_var_m2 = w * h

        if surface_ref_m2 == 0:
            print("[!] Surface de référence nulle, vérifie tes valeurs.")
            return None, None, None

        poids_par_m_ref = poids_total_kg / (nb_barres * 6.2)
        prix_par_m_ref = poids_par_m_ref * prix_kg

        ratio_surface = surface_var_m2 / surface_ref_m2
        cost_price = prix_par_m_ref * ratio_surface
        sale_price = cost_price * 2.5
        poids_par_m = poids_par_m_ref * ratio_surface

        print(f"{variant.default_code} | surface={int(surface_var_m2 * 1_000_000)} mm² | coût={cost_price:.2f} € | vente={sale_price:.2f} €")
        return round(cost_price, 2), round(sale_price, 2), round(poids_par_m, 3)

    except Exception as e:
        print(f"[X] Erreur de calcul fer plat pour {variant.display_name} : {e}")
        return None, None, None

def calculate_price_tube_rond(d_ref_mm, t_ref_mm, prix_ref_m, variant):
    try:
        d = safe_float(getattr(variant, 'product_diameter', 0.0)) * 1000
        t = safe_float(getattr(variant, 'product_thickness', 0.0)) * 1000

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

# -----------------------------
# Nouveau profil : Tôle
# -----------------------------
def calculate_price_tole(ref_sheet_w_mm, ref_sheet_l_mm, ref_thickness_mm, ref_buy_price_sheet, coef, variant):
    """
    Calcule standard_price et lst_price pour une tôle VENDUE A LA PIECE.
    - Reference: une tôle ref (ex 1000x2000x2) achetée X €
    - coef: coefficient de vente (ex 2.5)
    - variant.product_width / product_length en mètres
    - variant.product_thickness en mètres (ex 0.002)
    """
    try:
        # Référence
        ref_area_m2 = (ref_sheet_w_mm / 1000.0) * (ref_sheet_l_mm / 1000.0)
        if ref_area_m2 <= 0:
            print("[!] Surface de référence invalide.")
            return None, None

        ref_cost_m2 = ref_buy_price_sheet / ref_area_m2
        ref_sale_m2 = ref_cost_m2 * coef

        # Variante
        w_m = safe_float(getattr(variant, 'product_width', 0.0))
        l_m = safe_float(getattr(variant, 'product_length', 0.0))
        t_m = safe_float(getattr(variant, 'product_thickness', 0.0))

        if not all([w_m, l_m, t_m]):
            print(f"[!] Dimensions/épaisseur manquantes pour {variant.display_name}, ignoré.")
            return None, None

        area_m2 = w_m * l_m
        t_mm = t_m * 1000.0

        if area_m2 <= 0:
            print(f"[!] Surface nulle pour {variant.display_name}, ignoré.")
            return None, None

        # Ratio d'épaisseur (linéaire)
        ratio_t = t_mm / ref_thickness_mm

        cost_m2 = ref_cost_m2 * ratio_t
        sale_m2 = ref_sale_m2 * ratio_t

        cost_price = cost_m2 * area_m2
        sale_price = sale_m2 * area_m2

        print(
            f"{variant.default_code} | {int(w_m*1000)}x{int(l_m*1000)} | t={t_mm:.1f}mm | "
            f"m²={area_m2:.3f} | coût={cost_price:.2f}€ | vente={sale_price:.2f}€"
        )
        return round(cost_price, 2), round(sale_price, 2)

    except Exception as e:
        print(f"[X] Erreur de calcul tôle pour {variant.display_name} : {e}")
        return None, None

# -----------------------------
# UI / selection
# -----------------------------
def lister_templates_categ(categ_id: int):
    print(f"\n--- Produits dans la catégorie ID {categ_id} ---")
    templates = env['product.template'].search([('categ_id', '=', categ_id)], order='id')
    for tmpl in templates:
        print(f"ID: {tmpl.id} | Nom: {tmpl.name}")
    if not templates:
        print("(aucun produit)")
    return templates

def get_or_create_pricelist(name: str):
    pricelist = env['product.pricelist'].search([('name', '=', name)], limit=1)
    if not pricelist:
        pricelist = env['product.pricelist'].create({
            'name': name,
            'currency_id': env.ref('base.EUR').id,
        })
    return pricelist

def upsert_pricelist_item(pricelist, variant, sale_price):
    item_model = env['product.pricelist.item']
    item = item_model.search([
        ('pricelist_id', '=', pricelist.id),
        ('product_id', '=', variant.id),
        ('applied_on', '=', '0_product_variant'),
    ], limit=1)
    if item:
        item.write({'fixed_price': sale_price})
    else:
        item_model.create({
            'pricelist_id': pricelist.id,
            'applied_on': '0_product_variant',
            'product_id': variant.id,
            'fixed_price': sale_price,
        })

def calculate_and_update_prices():
    print("\n=== Mise à jour des prix (Métal au mètre + Tôles) ===")

    # Catégorie à lister (tu peux changer)
    categ_id = int(input("ID catégorie à lister (ex 6) : ").strip() or "6")
    lister_templates_categ(categ_id)

    tmpl_id = int(input("\nEntrez l'ID du product.template à traiter : ").strip())

    profiles = {
        "1": ("Tube carré / rectangulaire", "tube_section"),
        "2": ("Fer plat ou carré plein", "fer_plat"),
        "3": ("Cornière (égale ou inégale)", "corniere"),
        "4": ("Tube rond", "tube_rond"),
        "5": ("Tôle (prix pièce à partir d'une tôle de référence)", "tole"),
    }

    print("\n--- Sélection du profil : ---")
    for k, (name, _) in profiles.items():
        print(f" {k}. {name}")

    profile_choice = input("Choisissez le profil : ").strip()
    if profile_choice not in profiles:
        print("[X] Profil inconnu.")
        return

    profile_name, profile_code = profiles[profile_choice]
    print(f"\n--- Profil choisi : {profile_name} ---")

    # Inputs profil
    params = {}

    if profile_code == "tube_section":
        params['height'] = safe_float(input("Hauteur de référence (mm) : "))
        params['width'] = safe_float(input("Largeur de référence (mm) : "))
        params['thickness'] = safe_float(input("Épaisseur de référence (mm) : "))
        params['reference_price_m'] = safe_float(input("Prix d'achat du mètre linéaire (€) : "))

    elif profile_code == "fer_plat":
        params['width_ref'] = safe_float(input("Largeur de référence (mm) : "))
        params['height_ref'] = safe_float(input("Épaisseur de référence (mm) : "))
        params['poids_total_kg'] = safe_float(input("Poids total de la commande (kg) : "))
        params['nb_barres'] = int(input("Nombre de barres achetées : "))
        params['prix_kg'] = safe_float(input("Prix d'achat au kg (€) : "))

    elif profile_code == "corniere":
        params['width_ref'] = safe_float(input("Largeur de référence (mm) : "))
        params['height_ref'] = safe_float(input("Hauteur de référence (mm) : "))
        params['thickness_ref'] = safe_float(input("Épaisseur de référence (mm) : "))
        params['poids_total_kg'] = safe_float(input("Poids total acheté (kg) : "))
        params['nb_barres'] = int(input("Nombre de barres achetées : "))
        params['prix_kg'] = safe_float(input("Prix d'achat au kg (€) : "))

    elif profile_code == "tube_rond":
        params['d_ref_mm'] = safe_float(input("Diamètre de référence (mm) : "))
        params['t_ref_mm'] = safe_float(input("Épaisseur de référence (mm) : "))
        params['prix_ref_m'] = safe_float(input("Prix d'achat du mètre linéaire (€) : "))

    elif profile_code == "tole":
        params['ref_sheet_w_mm'] = safe_float(input("Largeur tôle de référence (mm) (ex 1000) : "))
        params['ref_sheet_l_mm'] = safe_float(input("Longueur tôle de référence (mm) (ex 2000) : "))
        params['ref_thickness_mm'] = safe_float(input("Épaisseur référence (mm) (ex 2) : "))
        params['ref_buy_price_sheet'] = safe_float(input("Prix d'achat tôle référence (€) (ex 29.37) : "))
        params['coef'] = safe_float(input("Coef vente (ex 2.5) : ") or "2.5")

    # Pricelist
    pricelist_name = input("Nom de la liste de prix (défaut: Métal au mètre) : ").strip() or "Métal au mètre"
    pricelist = get_or_create_pricelist(pricelist_name)

    variants = env['product.product'].search([('product_tmpl_id', '=', tmpl_id)], order='id')
    if not variants:
        print("[!] Aucune variante trouvée sur ce template.")
        return

    print(f"\n--- Variantes trouvées : {len(variants)} ---")
    total_updated = 0

    for variant in variants:
        cost_price = None
        sale_price = None
        poids_par_m = None

        if profile_code == "tube_section":
            cost_price, sale_price = calculate_price_tube_section(
                params['height'], params['width'], params['thickness'], params['reference_price_m'], variant
            )
            poids_par_m = 0.0

        elif profile_code == "fer_plat":
            cost_price, sale_price, poids_par_m = calculate_price_fer_plat(
                params['width_ref'], params['height_ref'], params['poids_total_kg'], params['nb_barres'], params['prix_kg'], variant
            )

        elif profile_code == "corniere":
            cost_price, sale_price, poids_par_m = calculate_price_corniere(
                params['width_ref'], params['height_ref'], params['thickness_ref'], params['poids_total_kg'], params['nb_barres'], params['prix_kg'], variant
            )

        elif profile_code == "tube_rond":
            cost_price, sale_price = calculate_price_tube_rond(
                params['d_ref_mm'], params['t_ref_mm'], params['prix_ref_m'], variant
            )
            poids_par_m = 0.0

        elif profile_code == "tole":
            cost_price, sale_price = calculate_price_tole(
                params['ref_sheet_w_mm'], params['ref_sheet_l_mm'], params['ref_thickness_mm'],
                params['ref_buy_price_sheet'], params['coef'], variant
            )
            poids_par_m = 0.0

        if cost_price is None or sale_price is None:
            print(f"[!] Pas de mise à jour pour {variant.display_name}")
            continue

        # Ecriture prix
        vals = {
            'standard_price': cost_price,
            'lst_price': sale_price,
        }

        # Ecrit le champ custom si présent
        if has_field(env['product.product'], 'product_kg_ml') and poids_par_m is not None:
            vals['product_kg_ml'] = float(poids_par_m)

        variant.write(vals)

        # Pricelist item par variante
        upsert_pricelist_item(pricelist, variant, sale_price)

        print(f"[{variant.id}] {variant.display_name}: coût={cost_price:.2f} € | vente={sale_price:.2f} €")
        total_updated += 1

    env.cr.commit()
    print(f"\n✅ Terminé. Variantes mises à jour : {total_updated}")

if __name__ == '__main__':
    try:
        calculate_and_update_prices()
    finally:
        cr.close()
