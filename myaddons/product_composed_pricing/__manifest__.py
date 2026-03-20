# -*- coding: utf-8 -*-
{
    'name': "product_composed_pricing",

    'summary': "Produits composés avec calcul dynamique du prix",

    'description': """
Module permettant de créer des produits composés avec calcul dynamique du prix.

Chaque produit peut être défini à partir de plusieurs composants (matière, découpe, service, etc.).
Une formule de quantité permet de calculer automatiquement la consommation de chaque composant
en fonction des paramètres saisis (dimensions, options...).

Le prix final est calculé à partir du coût des composants, avec application d’un coefficient
achat/vente.

Ce module constitue une base générique pour la vente de produits sur mesure
(ex : tôle découpée laser, pièces usinées, produits personnalisés).
""",

    'author': "Franck / ChatGPT Pour la métallerie de coneilla-del-vercol",
    'website': "https://www.metallerie.xyz",

    'category': 'Sales',
    'version': '0.1',

    'depends': ['base', 'product', 'sale', 'website'],

    'data': [
        #'security/ir.model.access.csv'
        'views/product_composition_line_views.xml',
        'views/product_template_views.xml',
    ],
}
