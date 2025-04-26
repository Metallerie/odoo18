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
    height = float(input("Entrez la hauteur (mm) du tube : "))
    width = float(input("Entrez la largeur (mm) du tube : "))
    thickness = float(input("Entrez l'épaisseur (mm) du tube : "))
    reference_price = float(input("Entrez le prix de référence pour 1 mètre linéaire du tube (en €) : "))

    # Conversion des dimensions en mètres
    height_m = height / 1000  # mm -> m
    width_m = width / 1000    # mm -> m
    thickness_m = thickness / 1000  # mm -> m

    # Calcul de la surface déployée (m²)
    surface = (height_m + width_m) * 2

    # Prix par m² pour 1 mm d'épaisseur
    base_price_per_m2 = reference_price / surface
    price_per_mm = base_price_per_m2 * surface

    # Prix total pour l'épaisseur donnée
    price = price_per_mm * thickness_m

    # Récupération des variantes (product_tmpl_id = 7)
    variants = env['product.product'].search([('product_tmpl_id', '=', 7)])

    # Affichage simplifié
    for variant in variants:
        print(f"{variant.display_name}: {price:.4f} €")

# Exécution
if __name__ == '__main__':
    try:
        calculate_price()
    finally:
        # Fermeture propre du curseur
        cr.close()
