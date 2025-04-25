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
    # Récupérer ou créer les attributs
    def get_or_create_attribute(name):
        attr = env['product.attribute'].search([('name', '=', name)], limit=1)
        if not attr:
            attr = env['product.attribute'].create({'name': name, 'create_variant': True})
        return attr

    section_attr = get_or_create_attribute('Section')
    epaisseur_attr = get_or_create_attribute('Epaisseur')

    # Lire le CSV
    with open(CSV_PATH, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter='\t')
        for row in reader:
            section = row['Dimensions'].strip()
            epaisseur = row['Epaisseur'].strip()
            ref_four = row['Réf. Four.'].strip()

            # Ajout des valeurs d’attribut
            section_val = env['product.attribute.value'].search([
                ('name', '=', section), ('attribute_id', '=', section_attr.id)
            ], limit=1)
            if not section_val:
                section_val = env['product.attribute.value'].create({
                    'name': section,
                    'attribute_id': section_attr.id
                })

            epaisseur_val = env['product.attribute.value'].search([
                ('name', '=', epaisseur), ('attribute_id', '=', epaisseur_attr.id)
            ], limit=1)
            if not epaisseur_val:
                epaisseur_val = env['product.attribute.value'].create({
                    'name': epaisseur,
                    'attribute_id': epaisseur_attr.id
                })

            template = env['product.template'].browse(TEMPLATE_ID)

            # Lier les attributs au template si pas déjà fait
            for attr, val in [(section_attr, section_val), (epaisseur_attr, epaisseur_val)]:
                line = env['product.template.attribute.line'].search([
                    ('product_tmpl_id', '=', template.id),
                    ('attribute_id', '=', attr.id)
                ], limit=1)
                if not line:
                    env['product.template.attribute.line'].create({
                        'product_tmpl_id': template.id,
                        'attribute_id': attr.id,
                        'value_ids': [(6, 0, [val.id])]
                    })
                elif val.id not in line.value_ids.ids:
                    line.write({'value_ids': [(4, val.id)]})

            # Retrouver la variante
            variant = env['product.product'].search([
                ('product_tmpl_id', '=', template.id),
                ('product_template_attribute_value_ids.attribute_id', '=', section_attr.id),
                ('product_template_attribute_value_ids.name', '=', section),
                ('product_template_attribute_value_ids.attribute_id', '=', epaisseur_attr.id),
                ('product_template_attribute_value_ids.name', '=', epaisseur),
            ], limit=1)

            if variant:
                variant.name = f"Tube soudés carrés {section.replace(' ', '')}x{epaisseur}"
                variant.default_code = ref_four
                variant.list_price = 0.0  # à ajuster si besoin
                print(f"✅ Produit mis à jour : {variant.name} ({ref_four})")
            else:
                print(f"⚠️ Variante non trouvée pour {section} / {epaisseur}")

    cr.commit()
    print("\n✅ Import terminé avec succès.")

except Exception as e:
    cr.rollback()
    print("\n❌ Erreur :", e)

finally:
    cr.close()
