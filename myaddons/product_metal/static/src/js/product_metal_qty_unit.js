odoo.define('product_metal.product_metal_qty_unit', function (require) {
    'use strict';

    const publicWidget = require('web.public.widget');

    publicWidget.registry.ProductMetalQtyUnit = publicWidget.Widget.extend({
        selector: '.oe_website_sale',

        start: function () {
            const self = this;
            this._super.apply(this, arguments);

            if (window.location.href.includes('metal-au-metre')) {
                setTimeout(function () {
                    self._injectUnitSelector();
                }, 500);
            }
        },

        _injectUnitSelector: function () {
            const qtyInput = $('input[name="add_qty"]');
            if (!qtyInput.length) {
                console.log('Pas d\'input quantité trouvé.');
                return;
            }

            // Permettre les décimales
            qtyInput.attr('step', 'any');

            // Cases à cocher
            const unitSelector = $(`
                <div class="input-group my-3" id="unit_selector_group">
                    <span class="input-group-text">Unité :</span>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="radio" name="unit_select" id="unit_m" value="1" checked>
                        <label class="form-check-label" for="unit_m">Mètre (m)</label>
                    </div>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="radio" name="unit_select" id="unit_cm" value="0.01">
                        <label class="form-check-label" for="unit_cm">Centimètre (cm)</label>
                    </div>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="radio" name="unit_select" id="unit_mm" value="0.001">
                        <label class="form-check-label" for="unit_mm">Millimètre (mm)</label>
                    </div>
                </div>
            `);

            qtyInput.closest('.js_product_quantity').after(unitSelector);

            // Gestion du changement d'unité
            $('input[name="unit_select"]').on('change', function () {
                const factor = parseFloat($(this).val());
                const currentVal = parseFloat(qtyInput.val()) || 0;
                const newVal = (currentVal * factor).toFixed(3);
                qtyInput.val(newVal);
            });
        },
    });

    return publicWidget.registry.ProductMetalQtyUnit;
});
