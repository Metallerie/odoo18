# -*- coding: utf-8 -*-
{
    'name': "metallerie_sync_1618",

    'summary': "Module de migration Odoo 16 vers 18",

    'description': """
metallerie_sync_1618/
│
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── sync_manager.py   # Orchestrateur
│   ├── sync_company.py   # Synchronisation de la société
│   ├── sync_products.py  # Synchronisation des produits
│   ├── sync_partners.py  # Synchronisation des partenaires
│   ├── sync_sales.py     # Synchronisation des ventes
│
├── data/
│   ├── cron_jobs.xml     # Configuration des tâches planifiées
│
└── views/
    ├── sync_compagny_views.xml    # 
    ├── sync_partners_views.xml    # """,

    'author': "Franck Bardina ",
    'website': "https://www.metallerie.xyz",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/18.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','web','account','product','sale_management','website','stock','purchase','website_sale','mrp','project_todo'],

    'data': [
        'views/sync_field_status_views.xml',
        'views/sync_company_views.xml' ,
        'views/sync_partners_views.xml' ,
        'data/cron_jobs.xml',
        'security/ir.model.access.csv',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

