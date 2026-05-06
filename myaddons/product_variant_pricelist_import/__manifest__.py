# -*- coding: utf-8 -*-
{
    "name": "Product Variant Pricelist Import",
    "version": "18.0.1.0.0",
    "summary": "Import de variantes et mise à jour de pricelist par CSV",
    "category": "Sales",
    "author": "Metallerie",
    "license": "LGPL-3",
    "depends": [
        "product",
        "product_metal",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
        "views/product_variant_pricelist_import_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
