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
                }, 500); // Laisse le temps à Odoo de charger la page
            }
        },

        _injectUnitSelector: function () {
            const qtyInput = $('input[name="add_qty"]');
            if (!qtyInput.length) {
                console.log('Pas d\'input quantité trouvé.');
                return;
            }

            // Autoriser les décimales dans l'input quantité
            qtyInput.attr('step', 'any');

            // Créer les cases à cocher
            const unitSelectorHtml = `
                <div class="input-group my-3" id="unit_selector_group">
                    <span class="input-group-text">Unité :</span>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="radio" name="unit_select" id="unit_m" value="1" checked="checked"/>
                        <label class="form-check-label" for="unit_m">Mètre (m)</label>
                    </div>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="radio" name="unit_select" id="unit_cm" value="0.01"/>
                        <label class="form-check-label" for="unit_cm">Centimètre (cm)</label>
                    </div>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="radio" name="unit_select" id="unit_mm" value="0.001"/>
                        <label class="form-check-label" for="unit_mm">Millimètre (mm)</label>
                    </div>
                </div>
            `;

            // Injecter juste après la quantité
            qtyInput.closest('.js_product_quantity').after(unitSelectorHtml);

            // Logique de conversion quand on clique sur une unité
            $('input[name="unit_select"]').on('change', function () {
                const selectedFactor = parseFloat($(this).val());
                let inputQty = parseFloat(qtyInput.val()) || 0;

                if (inputQty) {
                    inputQty = (inputQty * selectedFactor).toFixed(3);
                    qtyInput.val(inputQty);
                }
            });
        },
    });

    return publicWidget.registry.ProductMetalQtyUnit;
});
