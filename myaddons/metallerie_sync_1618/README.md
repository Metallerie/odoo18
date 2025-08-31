# Module Odoo : Metallerie Sync 1618

Ce module permet de synchroniser dynamiquement des données entre deux instances Odoo (V16 et V18) tout en tenant compte des différences de schéma entre les deux bases de données.

## Fonctionnalités principales

1. **Synchronisation unidirectionnelle** :
   - Les données sont transférées de l'instance Odoo V16 vers l'instance Odoo V18.
   - Aucun retour des données de V18 vers V16 n'est effectué.

2. **Détection dynamique des champs** :
   - Les champs communs entre les deux versions sont automatiquement détectés et synchronisés.
   - Les champs absents ou invalides dans la cible sont ignorés.

3. **Gestion des champs complexes** :
   - Les champs nécessitant des relations ou des validations spécifiques (e.g., `currency_id`, `partner_id`) sont traités avec des conditions personnalisées.

4. **Mises à jour et insertions dynamiques** :
   - Les enregistrements existants sont mis à jour si nécessaire.
   - Les enregistrements manquants sont insérés avec leurs données complètes.

5. **Sortie en console** :
   - Chaque champ synchronisé est affiché en détail pour faciliter le suivi.

## Schéma du module

Le module est organisé de manière modulaire pour faciliter l'ajout de nouveaux modèles à synchroniser.

### Structure des fichiers

```
metallerie_sync_1618/
├── models/
│   ├── __init__.py
│   ├── sync_manager.py
│   ├── sync_company.py
├── views/
│   ├── sync_views.xml
├── security/
│   ├── ir.model.access.csv
├── __init__.py
├── __manifest__.py
```

### Détails des composants

1. **`sync_manager.py`** :
   - Contient les fonctions utilitaires pour établir des connexions aux bases de données Odoo V16 et V18.

2. **`sync_company.py`** :
   - Implémente la synchronisation pour le modèle `res.company`.
   - Détection dynamique des champs et gestion des mises à jour/insertions.

3. **`sync_views.xml`** :
   - Interface utilisateur permettant de déclencher manuellement la synchronisation.

4. **`ir.model.access.csv`** :
   - Gestion des droits d'accès pour permettre aux utilisateurs autorisés d'exécuter la synchronisation.

## Exemple de synchronisation

### Étapes principales dans `sync_company.py`

1. **Récupération des champs disponibles** :
   - Les champs de `res.company` sont détectés dans les bases V16 et V18.

2. **Vérification des champs communs** :
   - Les champs communs entre les deux versions sont sélectionnés pour la synchronisation.

3. **Mises à jour ou insertions** :
   - Les enregistrements existants sont mis à jour avec les données les plus récentes.
   - Les enregistrements manquants sont insérés dynamiquement.

### Exécution de la synchronisation

#### Depuis l'interface utilisateur
- Accédez à "Synchronisation Sociétés" dans le module.
- Cliquez sur le bouton "Lancer Synchronisation".

#### Depuis le code
- Appelez la méthode statique `sync_v16_to_v18()` depuis le modèle `metallerie.sync.company`.

```python
from odoo import api, SUPERUSER_ID

with api.Environment.manage():
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['metallerie.sync.company'].sync_v16_to_v18()
```

## Points importants

1. **Gestion des champs complexes** :
   - Les champs comme `currency_id` ou `partner_id` sont validés pour s'assurer de leur compatibilité dans la base cible.

2. **Logs détaillés** :
   - Les actions sont enregistrées dans les logs pour faciliter le diagnostic.

3. **Extensibilité** :
   - Les modèles supplémentaires peuvent être ajoutés en suivant le modèle de `sync_company.py`.

## Ajouter un nouveau modèle

1. Créez un fichier `sync_<model>.py` dans le dossier `models`.
2. Implémentez la méthode `sync_v16_to_v18()` en utilisant le modèle de `sync_company.py`.
3. Ajoutez une entrée correspondante dans `sync_views.xml`.
4. Rechargez le module :

```bash
./odoo-bin -u metallerie_sync_1618
```

