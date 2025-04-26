import sys
import os
import builtins

# Ajout du chemin vers Odoo et configuration
sys.path.append('/data/odoo/metal-odoo18-p8179')
os.environ['ODOO_RC'] = '/data/odoo/metal-odoo18-p8179/odoo18.conf'

import odoo
from odoo import api, tools, sql_db

DB = 'metal-prod-18'

# Initialisation Odoo
# Charger la configuration sans arguments
tools.config.parse_config([])
odoo.service.server.load_server_wide_modules()
# Monkey-patch pour corriger NameError dans netsvc._open
import odoo.netsvc as netsvc
netsvc.open = builtins.open

# Connexion à la base de données
db = sql_db.db_connect(DB)
cr = db.cursor()
# Création de l'environnement Odoo
env = api.Environment(cr, 1, {})

# Fonction de calcul et mise à jour des prix

def calculate_and_update_prices():
    # Saisie des dimensions et du prix de référence pour un tube de base
    height = float(input("Entrez la hauteur (mm) du tube de référence : "))
    width = float(input("Entrez la largeur (mm) du tube de référence : "))
    thickness = float(input("Entrez l'épaisseur (mm) du tube de référence : "))
    reference_price = float(input("Entrez le prix de référence pour 1 mètre linéaire de ce tube (en €) : "))

    # Conversion des dimensions de référence en mètres
    height_ref = height / 1000
    width_ref = width / 1000
    thickness_ref = thickness / 1000 

    # Surface déployée du tube de référence (m²)
    surface_ref = (height_ref + width_ref) * 2

    # Calcul du prix unitaire par m³ (surface_ref * thickness_ref en m³)
    base_unit_price = reference_price / (surface_ref * thickness_ref)

    # Recherche ou création de la pricelist "Métal au mètre"
    pricelist = env['product.pricelist'].search([('name', '=', 'Métal au mètre')], limit=1)
    if not pricelist:
        pricelist = env['product.pricelist'].create({
            'name': 'Métal au mètre',
            'currency_id': env.ref('base.EUR').id,
        })

    # Récupération des variantes (product_tmpl_id = 7)
    variants = env['product.product'].search([('product_tmpl_id', '=', 7)])

    # Boucle de calcul et mise à jour
    for variant in variants:
        h = variant.product_height
        w = variant.product_width
        t = variant.product_thickness
        surface_var = (h + w) * 2
        cost_price = base_unit_price * surface_var * t
        sale_price = cost_price * 2.5

        # Mise à jour du coût sur la variante
        variant.write({'standard_price': cost_price})

        # Création ou mise à jour de la ligne de pricelist pour chaque variante
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

        print(f"{variant.display_name}: cout={cost_price:.4f} €, vente (pricelist)={sale_price:.4f} €")

    # Commit général à la fin pour tout valider en base
    env.cr.commit()

# Exécution
if __name__ == '__main__':
    try:
        calculate_and_update_prices()
    finally:
        cr.close()
