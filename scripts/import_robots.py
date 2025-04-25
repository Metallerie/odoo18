import odoo
import os
import sys

# Config perso
odoo_path = '/data/odoo/metal-odoo18-p8179'
db_name = 'metal-pro-18'

sys.path.append(odoo_path)
os.environ.setdefault('ODOO_RC', os.path.join(odoo_path, 'odoo18.conf'))

# Initialisation
odoo.tools.config['db_name'] = db_name
odoo.cli.server.setup_pid_file()

# On démarre l’environnement Odoo
odoo.service.server.load_server_wide_modules()
registry = odoo.modules.registry.Registry(db_name)

# Données à injecter
lines = """
Disallow: /my/*
Disallow: /*/my/*
Disallow: /groups/*
Disallow: */groups/*
Disallow: */typo?domain=
Disallow: *?*orderby=
Disallow: *?*order=
Disallow: */tag/*,*
Disallow: */page/*/*
Disallow: *?*page=
Disallow: *?*search=*
Disallow: ?*grade_id=*
Disallow: ?*country_id=*
Disallow: /im_livechat/init
Disallow: */google_map/*
Disallow: /calendar/view/*
Disallow: /event/*/exhibitor/*
Disallow: */page/website_event.*
Disallow: */website-page-fake-*
Disallow: */forum/*/user/*
Disallow: */forum/user/*
Disallow: */forum/*/tag/*
Disallow: */_activate_your_database/*
Disallow: */country_flags/*
Disallow: */web/image/res.lang/*
Disallow: */web/image/res.partner/*
Disallow: */web/image/res.users/*
Disallow: */web/login*
Disallow: */web/reset_password*
Disallow: */web/signup*
Disallow: *?selected_app=*
Disallow: /profile/avatar/*
Disallow: */profile/users*
Disallow: /profile/ranks_badges?*forum_origin=*
Disallow: /jobs?*
Disallow: /jobs/apply/*
Disallow: /web?*
Disallow: /appointment*?*domain=*
Disallow: /appointment/*?timezone*
Disallow: /customers?tag_id*
Disallow: /event?*
Disallow: /event/*?*tags=
Disallow: /event/*/ics/*
Disallow: /event/page/*
Disallow: /forum/*?*filters*
Disallow: /forum/*?*sorting*
Disallow: /forum/*/tag/*/questions*
Disallow: /accounting-firms/country/*?grade*
""".strip().splitlines()

# Exécution avec le nouveau style (sans .manage())
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

    Robot = env['website.robots']
    Robot.search([]).unlink()

    for line in lines:
        if line.strip():
            Robot.create({'content': line.strip()})

    cr.commit()
    print("✅ Robots.txt injecté avec succès dans Odoo 18")
