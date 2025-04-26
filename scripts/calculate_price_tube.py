# Script pour calculer le prix d'achat d'un tube en fonction des dimensions et du prix de référence

def calculate_price():
    # Demander les informations à l'utilisateur
    height = float(input("Entrez la hauteur (mm) du tube : "))
    width = float(input("Entrez la largeur (mm) du tube : "))
    thickness = float(input("Entrez l'épaisseur (mm) du tube : "))
    reference_price = float(input("Entrez le prix de référence pour 1 mètre linéaire du tube (en €) : "))

    # Conversion des dimensions en mètres
    height_m = height / 1000  # Conversion mm en mètre
    width_m = width / 1000    # Conversion mm en mètre
    thickness_m = thickness / 1000  # Conversion mm en mètre

    # Calcul de la surface déployée en m²
    surface = (height_m + width_m) * 2  # Surface déployée

    # Calcul du prix par m² pour 1 mm d'épaisseur
    base_price_per_m2 = reference_price / surface  # Prix par m² pour 1 mm d'épaisseur
    price_per_mm = base_price_per_m2 * surface  # Prix pour 1 mm d'épaisseur

    # Calcul du prix total pour l'épaisseur donnée
    price = price_per_mm * thickness_m  # Prix d'achat pour l'épaisseur donnée

    # Affichage des résultats dans la console
    print("\n--- Résultats du calcul ---")
    print(f"Hauteur : {height} mm, Largeur : {width} mm, Épaisseur : {thickness} mm")
    print(f"Surface déployée : {surface:.6f} m²")
    print(f"Prix d'achat pour {thickness} mm d'épaisseur : {price:.4f} €")
    print(f"Prix de référence : {reference_price:.4f} € pour 1 mètre linéaire")

# Exécution de la fonction
calculate_price()
