try:
    # Initialisation du curseur et de l'environnement
    db = sql_db.db_connect(DB)
    cr = db.cursor()
    env = api.Environment(cr, 1, {})

    def calculate_price():
        try:
            height = float(input("Entrez la hauteur (mm) du tube : "))
            width = float(input("Entrez la largeur (mm) du tube : "))
            thickness = float(input("Entrez l'épaisseur (mm) du tube : "))
            reference_price = float(input("Entrez le prix de référence pour 1 mètre linéaire du tube (en €) : "))

            # Calcul du prix
            height_m = height / 1000  # Conversion mm -> mètre
            width_m = width / 1000
            thickness_m = thickness / 1000

            surface = (height_m + width_m) * 2
            base_price_per_m2 = reference_price / surface
            price_per_mm = base_price_per_m2 * surface
            price = price_per_mm * thickness_m

            # Recherche des variantes de produits
            product_variants = env['product.product'].search([('product_tmpl_id', '=', 7)])
            for variant in product_variants:
                width = round(variant.product_width, 6)
                height = round(variant.product_height, 6)
                thickness = round(variant.product_thickness, 6)
                length = round(variant.product_length, 6)

                variant_price = price
                print(f"{variant.display_name}: {variant_price:.4f} €")

        except Exception as e:
            print(f"Erreur : {e}")

    calculate_price()

finally:
    # Assurez-vous de fermer le curseur pour éviter les fuites
    cr.close()
