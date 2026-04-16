# -*- coding: utf-8 -*-
{
    "name": "Purchase Frequency Report",
    "version": "18.0.1.0.0",
    "summary": "Rapport de fréquence d'achat par produit",
    "category": "Purchases",
    "author": "La Métallerie",
    "license": "LGPL-3",
    "depends": [
        "purchase",
        "product",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/purchase_frequency_views.xml",
    ],
    "installable": True,
    "application": False,
}
