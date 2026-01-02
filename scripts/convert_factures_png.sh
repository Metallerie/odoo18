#!/bin/bash
# 🚀 Script de conversion PDF -> PNG + création d'un zip

# 📂 Dossier contenant les PDF (adapter si besoin)
INPUT_DIR="$HOME/Bureau/voye_document/historique"
# 📂 Dossier de sortie pour les images PNG
OUTPUT_DIR="$HOME/Bureau/voye_document/factures_png"
# 📦 Nom du zip final
ZIP_NAME="factures_png.zip"

# Création du dossier de sortie s'il n'existe pas
mkdir -p "$OUTPUT_DIR"

echo "🔎 Conversion des PDF en images PNG (300 dpi, qualité 90)..."
for f in "$INPUT_DIR"/*.pdf; do
    filename=$(basename "$f" .pdf)
    echo "   → $filename.pdf"
    convert -density 300 -quality 90 "$f" "$OUTPUT_DIR/${filename}-%02d.png"
done

echo "📦 Création de l'archive ZIP..."
cd "$OUTPUT_DIR" || exit
zip -r "$ZIP_NAME" ./*.png

echo "✅ Terminé ! Archive disponible ici : $OUTPUT_DIR/$ZIP_NAME"
