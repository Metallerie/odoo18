# -*- coding: utf-8 -*-
# __manifest__.py
{
    "name": "Website Link Checker",
    "version": "1.0",
    "depends": ["website", "mail"],
    "author": "Franck",
    "category": "Website",
    "summary": "Scan des liens de sitemap et envoi d'un rapport en cas d'erreur",
    "data": [
        "views/website_views.xml",
        "views/website_page_views.xml",
        "views/blog_post_views.xml",
        "views/product_template_views.xml",
        "views/forum_post_views.xml",
        "data/ir_cron.xml",
    ],
    "installable": True,
    "application": False,
}
