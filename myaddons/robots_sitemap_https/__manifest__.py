# fichier __manifest__.py
# ------------------------
{
    'name': 'Website HTTPS Patch',
    'version': '1.0',
    'category': 'Website',
    'summary': 'Force HTTPS in url_root globally (monkey patch)',
    'depends': ['website'],
    'installable': True,
    'auto_install': False,
    'sequence': 99,
    'license': 'LGPL-3',
    'qweb': [
    'views/sitemap_templates.xml',
],

}
