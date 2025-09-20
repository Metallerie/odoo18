from doctr.models import ocr_predictor
from doctr.io import DocumentFile

# 1. Charger le modèle OCR doctr (détection + reco)
model = ocr_predictor(pretrained=True)

# 2. Charger ton PDF (ici ta facture CCL)
doc = DocumentFile.from_pdf("/data/Documents/factures_archive/Facture_CCL_153880.pdf")

# 3. Prédire
result = model(doc)

# --- Fonction de nettoyage ---
def normalize_text(text: str) -> str:
    if not text:
        return ""
    # Supprimer les multiples \n et coller avec espaces
    cleaned = " ".join(text.split())
    # Supprimer les doubles espaces
    cleaned = " ".join(cleaned.split())
    return cleaned.strip()

# 4. Extraire et reconstruire les lignes
supplier_candidates = []
for page in result.pages:
    for block in page.blocks:
        for line in block.lines:
            text = " ".join([word.value for word in line.words])
            text_norm = normalize_text(text)
            # On filtre : si ça ressemble à un nom de société
            if "comptoir" in text_norm.lower() or "ccl" in text_norm.lower():
                supplier_candidates.append(text_norm)

# 5. Choisir le candidat le plus long (souvent le nom complet)
if supplier_candidates:
    supplier_name = max(supplier_candidates, key=len)
    print("✅ Fournisseur détecté :", supplier_name)
else:
    print("⚠️ Aucun fournisseur détecté")
