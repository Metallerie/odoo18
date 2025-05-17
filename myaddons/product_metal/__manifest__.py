# -*- coding: utf-8 -*-
{
    'name': 'Product Métal',
    'version': '18.0.1.0.0',
    'category': 'Product',
    'author': """Modifié par franck et Gpt Création des champ de dimention dans product_product """,
    'license': 'AGPL-3',
    'website': 'https://www.metallerie.xyz',
    'depends': [
       "base",  "product", "uom",
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/product_view.xml',
    ],
    'installable': True,
    'images': ['static/description/icon.png'],
    'assets': {
    'web.assets_frontend': [
        'product_metal/static/src/js/product_quantity_precision.js',
    ]
    },
 }
