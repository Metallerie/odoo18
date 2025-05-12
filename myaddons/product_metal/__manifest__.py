
{
    "name": "Product Métal",
    "version": "18.0.1.0.0",
    "category": "Product",
    "author": "Modifié par franck et Gpt Regroupement des fonctionalités de la métallerie de corneilla del vercol ",
    "license": "AGPL-3",
    "website": "https://www.metallerie.xyz",
    "depends": ["base","product","website_sale","uom","stock"],
    "data": ["security/ir.model.access.csv",
             'views/account_move_purchase_button.xml',
             "views/product_view.xml"],
    "installable": True,
    "images": ["static/description/icon.png"],
    'assets': {
    'web.assets_frontend': [
        'product_metal/static/src/js/product_quantity_precision.js',
    ],
},

}
