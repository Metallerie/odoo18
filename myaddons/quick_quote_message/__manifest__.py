{
    "name": "Quick Quote Message",
    "version": "18.0.2.0.0",
    "summary": "Devis rapide à copier-coller pour SMS ou Leboncoin",
    "category": "Sales",
    "author": "La Métallerie",
    "license": "LGPL-3",
    "depends": ["sale_management", "product"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/quick_quote_wizard_views.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
