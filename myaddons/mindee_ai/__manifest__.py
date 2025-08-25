# -*- coding: utf-8 -*-
{
    'name': 'Mindee Ocr api',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': """ mindee api """,
    'description': """ mindee api                    """,
    'author': 'hasabalrasool',
    'website': "https://sbs-cloud.com",
    'company': 'Source Bussiness Solutions',
    'depends': ['base', 'account','product'],
    'data': [
        'views/account_move.xml',
        'views/res_config_settings.xml',
        'views/product_assign_line_wizard.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
