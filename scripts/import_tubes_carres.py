import sys
import os
import csv

sys.path.append('/data/odoo/metal-odoo18-p8179')
os.environ['ODOO_RC'] = '/data/odoo/metal-odoo18-p8179/odoo18.conf'

import odoo
from odoo import api, tools, sql_db

DB = 'metal-prod-18-clone'
TEMPLATE_ID = 7  # ID du template "Tube soudés carrés"
CSV_PATH = '/data/odoo/metal-odoo18-p8179/cvs/tubes_carres_correct.csv'

# Initialisation
tools.config.parse_config()
odoo.service.server.load_server_wide_modules()
db = sql_db.db_connect(DB)
cr = db.cursor()
env = api.Environment(cr, 1, {})  # Superadmin

try:
    # Récupérer ou créer l'attribut unique
    attr = env['product.attribute'].search([('name', '=', 'Tube carré')], limit=1)
    if not attr:
        attr = env['product.attribute'].create({'name': 'Tube carré'})

    values_ids = []

    # Lire le CSV et construire les valeurs d'attribut sous forme "40x40 mm x 1,5 mm"
    with open(CSV_PATH, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            section = row['section'].strip()
            epaisseur = row['epaisseur'].strip()
            ref_code = row['default_code'].strip()
            value_name = f"{section} x {epaisseur}"

            # Créer la valeur si elle n'existe pas
            value = env['product.attribute.value'].search([
                ('name', '=', value_name), ('attribute_id', '=', attr.id)
            ], limit=1)
            if not value:
                value = env['product.attribute.value'].create({
                    'name': value_name,
                    'attribute_id': attr.id
                })

            values_ids.append((value, ref_code))

    template = env['product.template'].browse(TEMPLATE_ID)

    # Nettoyer les lignes d'attributs existantes pour ce template
    env['product.template.attribute.line'].search([
        ('product_tmpl_id', '=', template.id)
    ]).unlink()

    # Ajouter toutes les valeurs comme une seule ligne d'attribut
    env['product.template.attribute.line'].create({
        'product_tmpl_id': template.id,
        'attribute_id': attr.id,
        'value_ids': [(6, 0, [v.id for v, _ in values_ids])]
    })

    # Mettre à jour les variantes avec les références et noms
    for value, ref_code in values_ids:
        variant = env['product.product'].search([
            ('product_tmpl_id', '=', template.id),
            ('product_template_attribute_value_ids', 'in', value.id)
        ], limit=1)

        if variant:
            variant.name = f"Tube soudés carrés {value.name}"
            variant.default_code = ref_code
            variant.list_price = 0.0  # à ajuster si besoin
            print(f"✅ Produit mis à jour : {variant.name} ({ref_code})")
        else:
            print(f"⚠️ Variante non trouvée pour {value.name}")

    cr.commit()
    print("\n✅ Import terminé avec succès.")

except Exception as e:
    cr.rollback()
    print("\n❌ Erreur :", e)

finally:
    cr.close()
