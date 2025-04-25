#!/bin/bash

echo "🐚 Passage à l'utilisateur odoo et lancement du shell..."
sudo su - odoo -c "
  source /data/odoo/odoo18-venv/bin/activate && \
  cd /data/odoo/metal-odoo18-p8179 && \
  ./odoo-bin shell -d metal-prod-18 --addons-path=/data/odoo/metal-odoo18-p8179/addons,/data/odoo/metal-odoo18-p8179/odoo/addons,/data/odoo/metal-odoo18-p8179/myaddons,/data/odoo/metal-odoo18-p8179/communityaddons
"
