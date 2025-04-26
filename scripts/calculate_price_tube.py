import sys
import os
import pandas as pd
import builtins

# Ajout du chemin vers Odoo et configuration
sys.path.append('/data/odoo/metal-odoo18-p8179')
os.environ['ODOO_RC'] = '/data/odoo/metal-odoo18-p8179/odoo18.conf'

import odoo
from odoo import api, tools, sql_db

DB = 'metal-prod-18'

# Initialisation Odoo
# Charge la configuration Odoo
tools.config.parse_config()
odoo.service.server.load_server_wide_modules()
# Monkey-patch pour corriger l'erreur NameError dans netsvc._open
import odoo.netsvc as netsvc
netsvc.open = builtins.open

# Connexion à la base de données
db = sql_db.db_connect(DB)
cr = db.cursor()
# Création de l'environnement Odoo
env = api.Environment(cr, 1, {})

# Fonction de calcul de prix
def calculate_price():
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

    # Calcul du prix unitaire par m² par mm d'épaisseur
    # Price_ref = base_unit_price * surface_ref * thickness_ref
    base_unit_price = reference_price / (surface_ref * thickness_ref)

    # Récupération des variantes (product_tmpl_id = 7)
    variants = env['product.product'].search([('product_tmpl_id', '=', 7)])

    # Calcul et affichage
    for variant in variants:
        # Dimensions variante (mm -> m)
        h = variant.product_height / 1000
        w = variant.product_width / 1000
        t = variant.product_thickness / 1000
        # Surface déployée de la variante
        surface_var = (h + w) * 2
        # Prix calculé
        price_var = base_unit_price * surface_var * t
        # Affichage simple
        print(f"{variant.display_name}: {price_var:.4f} €")

# Exécution
def main():
    try:
        calculate_price()
    finally:
        cr.close()

if __name__ == '__main__':
    main()
