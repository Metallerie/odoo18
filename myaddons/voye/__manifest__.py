# -*- coding: utf-8 -*-
{
    'name': "voye",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','account'],

    # always loaded
    'data': [
        'security/security.xml',
        'views/views.xml',
        'views/templates.xml',
        "security/ir.model.access.csv",
        "views/voye_query_views.xml",
        "views/menu.xml",
        "views/voye_ai_wizard_views.xml",
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

