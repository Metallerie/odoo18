import sys
import os
import builtins

# --- Configuration de l'environnement Odoo ---

# Ajout du chemin d'accès au projet Odoo
sys.path.append('/data/odoo/metal-odoo18-p8179')
# Définition du fichier de configuration Odoo
os.environ['ODOO_RC'] = '/data/odoo/metal-odoo18-p8179/odoo18.conf'

import odoo
from odoo import api, tools, sql_db

DB = 'metal-prod-18'

# Chargement de la configuration Odoo
tools.config.parse_config([])
odoo.service.server.load_server_wide_modules()

# Correction d'une erreur liée à l'import de netsvc
import odoo.netsvc as netsvc
netsvc.open = builtins.open

# Connexion à la base de données Odoo
db = sql_db.db_connect(DB)
cr = db.cursor()
# Création de l'environnement Odoo (accès aux modèles)
env = api.Environment(cr, 1, {})

# --- Fonction principale de calcul et mise à jour des prix ---

def calculate_and_update_prices():
    """
    Demande les dimensions d'un tube de référence et son prix d'achat,
    calcule le coût et le prix de vente pour toutes les variantes,
    met à jour le standard_price de chaque variante,
    crée une entrée dans la liste de prix "Métal au mètre",
    et désactive automatiquement les variantes avec 4 mm ou 5 mm d'épaisseur.
    """
    # Saisie des informations de référence
    height = float(input("Entrez la hauteur (mm) du tube de référence : "))
    width = float(input("Entrez la largeur (mm) du tube de référence : "))
    thickness = float(input("Entrez l'épaisseur (mm) du tube de référence : "))
    reference_price = float(input("Entrez le prix de référence pour 1 mètre linéaire de ce tube (en €) : "))

    # Conversion en mètres
    height_ref = height / 1000
    width_ref = width / 1000
    thickness_ref = thickness / 1000

    # Calcul de la surface déployée par mètre linéaire
    surface_ref = (height_ref + width_ref) * 2

    # Calcul du prix par m³ basé sur le tube de référence
    base_unit_price = reference_price / (surface_ref * thickness_ref)

    # Recherche ou création de la pricelist "Métal au mètre"
    pricelist = env['product.pricelist'].search([('name', '=', 'Métal au mètre')], limit=1)
    if not pricelist:
        pricelist = env['product.pricelist'].create({
            'name': 'Métal au mètre',
            'currency_id': env.ref('base.EUR').id,
        })

    # Récupération des variantes associées au template ID 7
    variants = env['product.product'].search([('product_tmpl_id', '=', 7)])

    # Calcul et mise à jour pour chaque variante
    for variant in variants:
        # Récupération des dimensions (déjà en mètres)
        h = variant.product_height
        w = variant.product_width
        t = variant.product_thickness

        # Surface déployée de la variante
        surface_var = (h + w) * 2

        # Calcul des prix
        cost_price = base_unit_price * surface_var * t
        sale_price = cost_price * 2.5

        # Mise à jour du prix d'achat (coût) sur la variante
        variant.write({'standard_price': cost_price})

        # Création ou mise à jour de la règle spécifique dans la pricelist
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

        # Désactivation automatique si épaisseur est 4mm ou 5mm
        if variant.product_thickness in (0.004, 0.005):
            variant.write({'active': False})
            print(f"{variant.display_name}: désactivé (épaisseur spéciale)")
        else:
            variant.write({'active': True})
            print(f"{variant.display_name}: cout={cost_price:.4f} €, vente (pricelist)={sale_price:.4f} €")

    # Validation des écritures en base
    env.cr.commit()

# --- Point d'entrée du script ---

if __name__ == '__main__':
    try:
        calculate_and_update_prices()
    finally:
        cr.close()
