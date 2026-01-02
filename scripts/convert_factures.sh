


#!/bin/bash
# 🚀 Script de conversion PDF -> TXT avec OCR + création d'un zip

# 📂 Dossier contenant les PDF
INPUT_DIR="/data/Documents/factures_archive/historique"
# 📂 Dossier de sortie pour les fichiers TXT
OUTPUT_DIR="/data/Documents/factures_txt"
# 📦 Nom du zip final
ZIP_NAME="factures_txt.zip"

# Création du dossier de sortie s'il n'existe pas
mkdir -p "$OUTPUT_DIR"

echo "🔎 Conversion des PDF en texte OCR (français)..."
for f in "$INPUT_DIR"/*.pdf; do
    filename=$(basename "$f" .pdf)
    echo "   → $filename.pdf"
    tesseract "$f" "$OUTPUT_DIR/$filename" -l fra
done

echo "📦 Création de l'archive ZIP..."
cd "$OUTPUT_DIR" || exit
zip -r "$ZIP_NAME" ./*.txt

echo "✅ Terminé ! Archive disponible ici : $OUTPUT_DIR/$ZIP_NAME"

