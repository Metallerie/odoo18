# -*- coding: utf-8 -*-
{
    'name': "product_composed_pricing",

    'summary': "Module permettant de créer des produits composés avec calcul dynamique du prix. ",

    'description': """


Chaque produit peut être défini à partir de plusieurs composants (matière, découpe, service, etc.).
Une formule de quantité permet de calculer automatiquement la consommation de chaque composant
en fonction des paramètres saisis (dimensions, options...).

Le prix final est calculé à partir du coût des composants, avec application d’un coefficient
achat/vente.

Ce module constitue une base générique pour la vente de produits sur mesure
(ex : tôle découpée laser, pièces usinées, produits personnalisés).
""",

    'author': "My Company,chatgpt et franck ",
    'website': "https://www.metallerie.xyz",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base''web','sale','website'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/product_composition_line_views.xml',
        'views/product_template_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

