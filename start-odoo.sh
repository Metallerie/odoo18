#!/bin/bash
# start-odoo.sh
# Démarrage Odoo en console et rester logué en utilisateur odoo après CTRL+C

sudo su - odoo <<'EOF'
    source /data/odoo/odoo18-venv/bin/activate
    cd /data/odoo/metal-odoo18-p8179
    ./odoo-bin \
        --database=metal-prod-18 \
        --addons-path=/data/odoo/metal-odoo18-p8179/addons,\
/data/odoo/metal-odoo18-p8179/odoo/addons,\
/data/odoo/metal-odoo18-p8179/myaddons,\
/data/odoo/metal-odoo18-p8179/communityaddons,\
/data/odoo/metal-odoo18-p8179/ocaaddons

    # Après CTRL+C, on garde un shell ouvert en odoo
    exec bash --login
EOF
