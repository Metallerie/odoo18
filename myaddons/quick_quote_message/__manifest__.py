{
    "name": "Quick Quote Message",
    "version": "18.0.2.0.0",
    "summary": "Devis rapide à copier-coller pour SMS ou Leboncoin",
    "category": "Sales",
    "author": "La Métallerie",
    "license": "LGPL-3",
    "depends": ["sale_management", "product", "web"],
    "data": [
        "views/quick_quote_wizard_views.xml",
        "views/sale_order_list_inherit.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "quick_quote_message/static/src/js/sale_order_list_button.js",
            "quick_quote_message/static/src/xml/sale_order_list_button.xml",
        ],
    },
    "installable": True,
    "application": False,
}
