/** @odoo-module **/

import publicWidget from 'web.public.widget';

publicWidget.registry.WebsiteSale.include({
    /**
     * Surcharge de la méthode pour gérer la précision UoM.
     */
    _onChangeCartQuantity: function (ev) {
        const $input = $(ev.currentTarget);
        const uomPrecision = parseInt($input.data('uom_precision') || 3); // Par défaut, précision à 3 décimales
        let value = parseFloat($input.val() || 0);

        if (isNaN(value)) {
            value = 0.001; // Valeur minimale par défaut
        }

        // Arrondi selon la précision définie
        value = parseFloat(value).toFixed(uomPrecision);

        // Mettre à jour la quantité dans le panier
        this._changeCartQuantity($input, value);
    },

    _changeCartQuantity: function ($input, value) {
        // Envoie la nouvelle quantité au backend sans arrondi
        const params = {
            line_id: $input.data('line-id'),
            product_id: $input.data('product-id'),
            add_qty: value,
        };
        this._rpc({
            route: "/shop/cart/update_json",
            params: params,
        }).then(function (data) {
            // Met à jour l'affichage
            if (!data.error) {
                $input.val(value); // Met à jour la quantité dans le DOM
            }
        });
    },
});
