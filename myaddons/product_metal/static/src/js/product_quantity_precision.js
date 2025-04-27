/** @odoo-module **/

import publicWidget from 'web.public.widget';

publicWidget.registry.WebsiteSale.include({
    /**
     * Surcharge de la méthode pour gérer la précision UoM.
     */
    _onChangeCartQuantity: function (ev) {
        const $input = $(ev.currentTarget);
        const uomPrecision = parseInt($input.data('uom_precision') || 2); // Récupère la précision
        let value = parseFloat($input.val() || 0);

        if (isNaN(value)) {
            value = 0.01; // Valeur minimale par défaut
        }

        // Arrondi à la précision définie
        value = value.toFixed(uomPrecision);

        // Mettre à jour la quantité dans le panier
        this._changeCartQuantity($input, value);
    },
});
