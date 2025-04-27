odoo.define('product_metal.product_metal_qty_unit', function (require) {
    'use strict';

    const publicWidget = require('web.public.widget');

    publicWidget.registry.ProductMetalQtyUnit = publicWidget.Widget.extend({
        selector: '.oe_website_sale', // Le form principal
        events: {
            'change #unit_selector': '_onUnitChange',
            'input input[name="add_qty"]': '_onQuantityInput',
        },

        start: function () {
            this._conversionFactor = 1; // Par défaut : mètres
            return this._super.apply(this, arguments);
        },

        _onUnitChange: function (ev) {
            this._conversionFactor = parseFloat(ev.currentTarget.value) || 1;
            this._updateQuantity();
        },

        _onQuantityInput: function () {
            this._updateQuantity();
        },

        _updateQuantity: function () {
            const quantityInput = this.$('input[name="add_qty"]');
            if (!quantityInput.length) {
                return;
            }

            let rawValue = parseFloat(quantityInput.val()) || 0;
            let convertedValue = rawValue / this._conversionFactor; // Attention : division ici pour revenir en mètre

            quantityInput.val(convertedValue.toFixed(3));
        },
    });

    return publicWidget.registry.ProductMetalQtyUnit;
});
