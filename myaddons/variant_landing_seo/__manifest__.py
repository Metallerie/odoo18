# -*- coding: utf-8 -*-
{
    "name": "Variant Landing SEO",
    "version": "1.0",
    "summary": "Pages SEO dédiées pour les variantes de produit",
    "description": """
Permet de générer des pages URL-friendly et indexables pour chaque variante de produit
en suivant le format /shop/<slug>-<id>. Ajoute aussi un sitemap dédié aux variantes.
""",
    "author": "La Metallerie de corneilla del vercol, Bardina Franck & ChatGpt",
    "website": "https://www.metallerie.xyz",
    "category": "Website",
    "depends": ["website","website_sale", "product"],
    "data": [
        "views/templates.xml",  # À venir ou vide pour l'instant
        "views/variant_seo_product.xml",
    ]
    ,
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
