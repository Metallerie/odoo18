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
    'depends': ['base', 'account','product','partner' ],
    'data': [
        'views/account_move.xml',
        'views/res_config_settings.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
