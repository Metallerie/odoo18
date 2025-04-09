{
    'name': 'WhatsApp Secure Redirect',
    'version': '1.0',
    'summary': 'Envoi sécurisé de messages WhatsApp avec redirection et tracking',
    'description': """
📌 Ce module ajoute :
- Un **contrôleur Odoo sécurisé** pour générer un lien WhatsApp sans exposer le numéro
- Le **numéro WhatsApp configuré dans la fiche société**
- Un **bouton réutilisable dans les pages ou templates QWeb**
- Le message WhatsApp inclut **le lien vers votre site**, générant la miniature dans WhatsApp

## Utilisation :
Placez le bouton dans vos pages :
<t t-call="whatsapp_secure.whatsapp_button_template"/>
    """,
    'author': 'Franck & ChatGPT',
    'website': 'https://www.metallerie.xyz',
    'category': 'Website',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'website'],
    'data': [
        'security/ir.model.access.csv',
        'views/whatsapp_send_message_view.xml',
        'views/whatsapp_menu.xml',
        'views/whatsapp_button.xml',
        'views/res_company_view.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
