# -*- coding: utf-8 -*-
# __manifest__.py
{
    'name': 'Website Link Checker',
    'version': '18.0.1.0.0',
    'depends': ['website', 'mail'],
    'website': 'https://www.metallerie.xyz',
    'author': 'Franck & Gpt',
    'category': 'Website',
    'summary': "Scan des liens de sitemap et envoi d'un rapport en cas d'erreur",
    'description': """envoi d'un rapport en cas d'erreur""",
    'installable': True,
    'license': 'LGPL-3',
    'application': False,
    'data': [
        'views/website_page_views.xml',
        'data/ir_cron.xml',
    ],
}
