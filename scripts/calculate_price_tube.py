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
    height_ref = height 
    width_ref = width 
    thickness_ref = thickness 

    # Surface déployée du tube de référence (m²)
    surface_ref = (height_ref + width_ref) * 2

    # Calcul du prix unitaire par m³ (surface_ref * thickness_ref en m³)
    base_unit_price = reference_price / (surface_ref * thickness_ref)

    # Récupération des variantes (product_tmpl_id = 7)
    variants = env['product.product'].search([('product_tmpl_id', '=', 7)])

    # Boucle de calcul et mise à jour
    for variant in variants:
        # Dimensions variante en mètres (déjà stockées en mètre)
        h = variant.product_height
        w = variant.product_width
        t = variant.product_thickness
        # Surface déployée de la variante (m²)
        surface_var = (h + w) * 2
        # Calcul du prix d'achat
        cost_price = base_unit_price * surface_var * t
        # Calcul du prix de vente (x2.5)
        sale_price = cost_price * 2.5
        # Mise à jour du coût sur la variante
        variant.write({'standard_price': cost_price})
        # Mise à jour du prix de vente sur le template associé
        variant.product_tmpl_id.write({'list_price': sale_price})
        # Commit après chaque écriture pour sauvegarder en base
        env.cr.commit()
        # Affichage simple
        print(f"{variant.display_name}: cout={cost_price:.4f} €, vente={sale_price:.4f} €")

# Exécution
if __name__ == '__main__':
    try:
        calculate_and_update_prices()
    finally:
        cr.close()
