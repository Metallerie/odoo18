# DocAI AI 1.1 — Retrait / Dépôt d'espèces

## Installation

1. Sauvegarder la base et l'ancien dossier `docai_ai`.
2. Remplacer le dossier par celui contenu dans ce ZIP.
3. Installer les dépendances Python dans l'environnement Odoo :

```bash
pip install -r docai_ai/requirements.txt
```

4. Mettre à jour le module :

```bash
./odoo-bin -d NOM_BASE -u docai_ai --stop-after-init
```

5. Redémarrer Odoo.

## Fonctionnement

- `docai_json_runner.py` reste le moteur générique.
- `account_move_bank_receipt.py` enrichit le JSON pour les récépissés Caisse d'Épargne.
- Le bouton **Retrait / Dépôt d'espèces** crée deux pièces brouillon liées : journal caisse et journal banque.
- Le compte de virements internes est sélectionnable (normalement 580).
- Le PDF original est copié à l'identique sur la deuxième pièce.
- Une copie annotée est ajoutée sur chaque pièce lorsque `pypdf` et `reportlab` sont installés.

## Sens des écritures

### Dépôt d'espèces

- Caisse : Débit 580 / Crédit compte de liquidité caisse.
- Banque : Débit compte de liquidité banque / Crédit 580.

### Retrait d'espèces

- Banque : Débit 580 / Crédit compte de liquidité banque.
- Caisse : Débit compte de liquidité caisse / Crédit 580.

Les deux pièces restent en brouillon. Le lettrage du compte 580 pourra être réalisé après validation.
