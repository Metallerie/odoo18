odoo.define('product_metal.product_metal_qty_unit', function (require) {
    'use strict';

    const publicWidget = require('web.public.widget');

    publicWidget.registry.ProductMetalQtyUnit = publicWidget.Widget.extend({
        selector: '.oe_website_sale',
        events: {
            'change #unit_selector': '_onUnitChange',
            'input input[name="add_qty"]': '_onQuantityInput',
        },

        start: function () {
            this._conversionFactor = 1; // Par défaut en mètres
            return this._super.apply(this, arguments);
        },

        _onUnitChange: function (ev) {
            this._conversionFactor = parseFloat(ev.currentTarget.value);
            this._updateQuantity();
        },

        _onQuantityInput: function () {
            this._updateQuantity();
        },

        _updateQuantity: function () {
            const unitInput = this.$('#unit_selector');
            const quantityInput = this.$('input[name="add_qty"]');

            let rawValue = parseFloat(quantityInput.val()) || 0;
            let convertedValue = rawValue * this._conversionFactor;

            if (!isNaN(convertedValue)) {
                quantityInput.val((convertedValue).toFixed(3)); // Forcer affichage
            }
        },
    });

    return publicWidget.registry.ProductMetalQtyUnit;
});
