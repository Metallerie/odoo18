import sys
import os
import pandas as pd

sys.path.append('/data/odoo/metal-odoo18-p8179')
os.environ['ODOO_RC'] = '/data/odoo/metal-odoo18-p8179/odoo18.conf'

import odoo
from odoo import api, tools, sql_db

DB = 'metal-prod-18'

# Initialisation Odoo
tools.config.parse_config()
odoo.service.server.load_server_wide_modules()
db = sql_db.db_connect(DB)
cr = db.cursor()
env = api.Environment(cr, 1, {})


# Demander les informations de base à l'utilisateur
def calculate_price():
    height = float(input("Entrez la hauteur (mm) du tube : "))
    width = float(input("Entrez la largeur (mm) du tube : "))
    thickness = float(input("Entrez l'épaisseur (mm) du tube : "))
    reference_price = float(input("Entrez le prix de référence pour 1 mètre linéaire du tube (en €) : "))

    # Conversion des dimensions en mètres
    height_m = height / 1000  # Conversion mm en mètre
    width_m = width / 1000    # Conversion mm en mètre
    thickness_m = thickness / 1000  # Conversion mm en mètre

    # Calcul de la surface déployée en m²
    surface = (height_m + width_m) * 2  # Surface déployée

    # Calcul du prix par m² pour 1 mm d'épaisseur
    base_price_per_m2 = reference_price / surface  # Prix par m² pour 1 mm d'épaisseur
    price_per_mm = base_price_per_m2 * surface  # Prix pour 1 mm d'épaisseur

    # Calcul du prix total pour l'épaisseur donnée
    price = price_per_mm * thickness_m  # Prix d'achat pour l'épaisseur donnée

    # Se connecter à Odoo et récupérer les variantes
    env = init_odoo()

    # Rechercher toutes les variantes de produits avec ID = 7
    product_variants = env['product.product'].search([('product_tmpl_id', '=', 7)])

    for variant in product_variants:
        # Récupérer les informations spécifiques à chaque variante
        width = round(variant.product_width, 6)
        height = round(variant.product_height, 6)
        thickness = round(variant.product_thickness, 6)
        length = round(variant.product_length, 6)

        # Calcul du prix pour chaque variante
        variant_price = price  # Calculer le prix d'achat pour cette variante

        # Affichage simplifié des résultats pour chaque variante dans la console
        print(f"{variant.display_name}: {variant_price:.4f} €")
    except ValueError as e:
        print(f"Erreur : {e}")
    except Exception as e:
        print(f"Une erreur inattendue s'est produite : {e}")
    finally:
        # Fermeture propre du curseur de la base de données
        cr.close()

# Exécution du script
calculate_price()
