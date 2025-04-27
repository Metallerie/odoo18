# Product Metal

**Module Odoo** pour la gestion des produits métalliques vendus au mètre.

---

## 📋 Présentation

Le module **Product Metal** est une évolution du module `product_dimension`, adapté pour les besoins spécifiques de la vente de métaux au mètre.

Il regroupe :
- La gestion des dimensions métalliques (largeur, hauteur, épaisseur, longueur).
- Le calcul automatique du coût et du prix de vente basé sur la surface déployée.
- La désactivation automatique des épaisseurs spéciales (4 mm et 5 mm).
- La préparation à l'affichage dynamique du stock par variante sur le site e-commerce.

---

## ⚙️ Fonctionnalités

- Ajout de champs sur `product.product` :
  - Largeur (`product_width`)
  - Hauteur (`product_height`)
  - Épaisseur (`product_thickness`)
  - Longueur (`product_length`)
- Script automatique de recalcul du `standard_price` et mise à jour de la `pricelist`.
- Désactivation automatique des variantes non standards (épaisseurs spéciales).
- Optimisé pour les ventes au mètre linéaire.

---

## 🔥 Objectifs futurs

- Surcharge du site pour afficher en temps réel :
  - Stock disponible par variante.
  - Message automatique pour les commandes spéciales.
- Intégration d'une tâche `cron` quotidienne pour la mise à jour des prix.

---

## 🛠️ Installation

1. Copier le module dans le dossier `addons`.
2. Installer depuis l'interface Odoo (`Apps`).
3. Configurer les dimensions et prix de référence.

---

## 👨‍🏭 Projet porté par

**Franck - Artisan Métallier**  
Passionné par l'optimisation et l'automatisation des métiers du métal.

---

