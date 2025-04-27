odoo.define('product_metal.product_metal_qty_unit', function (require) {
    'use strict';

    const publicWidget = require('web.public.widget');

    publicWidget.registry.ProductMetalQtyUnit = publicWidget.Widget.extend({
        selector: '.oe_website_sale',
        start: function () {
            const self = this;
            this._super.apply(this, arguments);

            // Vérifier si c'est un produit métal au mètre
            if (window.location.href.includes('metal-au-metre')) {
                setTimeout(function() {
                    self._injectUnitSelector();
                }, 1000); // Laisser le temps au configurateur de charger
            }
        },

        _injectUnitSelector: function () {
            const qtyInput = $('input[name="add_qty"]');
            if (!qtyInput.length) {
                console.log("Pas d'input quantité trouvé, abandon injection sélecteur.");
                return;
            }

            // Créer ton sélecteur d'unité
            const unitSelector = $(`
                <div class="input-group my-3" id="unit_selector_group">
                    <label class="input-group-text" for="unit_selector">Unité</label>
                    <select id="unit_selector" class="form-select">
                        <option value="1" selected="selected">Mètre (m)</option>
                        <option value="0.01">Centimètre (cm)</option>
                        <option value="0.001">Millimètre (mm)</option>
                    </select>
                </div>
            `);

            qtyInput.closest('.js_product_quantity').after(unitSelector);

            // Logique de conversion
            $('#unit_selector').on('change', function() {
                const factor = parseFloat($(this).val());
                const currentVal = parseFloat(qtyInput.val()) || 0;
                const newVal = (currentVal * factor).toFixed(3);
                qtyInput.val(newVal);
            });
        },
    });

    return publicWidget.registry.ProductMetalQtyUnit;
});
