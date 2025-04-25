#!/bin/bash

echo "🔧 Correction des permissions sur les modules personnalisés..."

TARGET="/data/odoo/metal-odoo18-p8179/"

sudo chown -R odoo:ubuntu "$TARGET"
sudo chmod -R 755 "$TARGET"

echo "✅ Permissions corrigées pour : $TARGET"
