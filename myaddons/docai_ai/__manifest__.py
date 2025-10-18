# -*- coding: utf-8 -*-
{
    'name': "DocAI AI",

    'summary': "Analyse automatique des factures PDF avec Google Document AI (Invoice Parser)",

    'description': """
Ce module permet d'importer des factures PDF dans Odoo, 
de les envoyer à Google Document AI (Invoice Parser) 
et de stocker le JSON de réponse pour générer automatiquement
des factures fournisseurs (account.move).
    """,

    'author': "Bardina Métallerie",
    'website': "http://www.metallerie.xyz",

    'category': 'Accounting',
    'version': '1.0',

    # dépendances nécessaires
    'depends': ['base', 'account'],

    # fichiers chargés à l'installation
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'data/cron.xml',
    ],

    # mode démo (pas obligatoire)
    'demo': [
        # 'demo/demo.xml',
    ],

    'installable': True,
    'application': False,
}
