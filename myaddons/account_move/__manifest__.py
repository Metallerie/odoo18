# -*- coding: utf-8 -*-
{
    'name': "account_move",

    'summary': "Création bon de commande a partire d'une facture suivi de la validation en stock",

    'description': """
    """,

    'author': "My Franck Company & gpt",
    'website': "https://www.metallerie.xyz",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/18.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Product',
    'version': '18.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base','account','purchase','stock'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/account_move_purchase_button.xml',
        #'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

