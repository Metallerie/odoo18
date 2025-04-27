/** @odoo-module **/

import publicWidget from 'web.public.widget';

publicWidget.registry.WebsiteSale.include({
    /**
     * Surcharge pour respecter la précision UoM dans le panier.
     */
    _onChangeCartQuantity: function (ev) {
        const $input = $(ev.currentTarget);
        const uomPrecision = parseInt($input.data('uom_precision') || 3); // Par défaut, 3 décimales
        let value = parseFloat($input.val() || 0);

        if (isNaN(value)) {
            value = 0.001; // Valeur minimale par défaut
            console.warn("Valeur entrée invalide, forcée à 0.001");
        }

        // Respecter la précision définie
        const roundedValue = parseFloat(value).toFixed(uomPrecision);
        if (value !== parseFloat(roundedValue)) {
            console.warn(
                `Quantité arrondie : ${value} -> ${roundedValue} (précision : ${uomPrecision})`
            );
        }

        // Mise à jour de la quantité dans le panier
        this._changeCartQuantity($input, roundedValue);
    },

    /**
     * Mise à jour de la quantité sans arrondi.
     */
    _changeCartQuantity: function ($input, value) {
        const lineId = $input.data('line-id');
        const productId = $input.data('product-id');

        // Ajout d'un log pour surveiller les appels RPC
        console.log(
            `Mise à jour du panier : ligne=${lineId}, produit=${productId}, quantité=${value}`
        );

        this._rpc({
            route: "/shop/cart/update_json",
            params: {
                line_id: lineId,
                product_id: productId,
                set_qty: value,
            },
        }).then(function (data) {
            if (!data.error) {
                $input.val(value); // Met à jour le DOM avec la valeur correcte
            } else {
                console.error("Erreur lors de la mise à jour du panier :", data.error);
            }
        });
    },
});
