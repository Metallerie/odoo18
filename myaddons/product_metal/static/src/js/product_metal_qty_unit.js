odoo.define('product_metal.unit_selector', function (require) {
    "use strict";

    const publicWidget = require('web.public.widget');

    publicWidget.registry.UnitSelector = publicWidget.Widget.extend({
        selector: '.oe_website_sale', // OK il existe
        start: function () {
            const self = this;

            // Attendre que le DOM soit totalement prêt
            setTimeout(function () {
                const qtyInput = document.querySelector('input[name="add_qty"]');
                if (!qtyInput) {
                    console.log("Pas de champ quantité trouvé !");
                    return;
                }

                // Création du bloc de cases à cocher
                const unitSelectorHTML = `
                    <div id="unit_selector_group" class="input-group my-3">
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
                    </div>`;

                // Injection du HTML juste après l'input
                qtyInput.insertAdjacentHTML('afterend', unitSelectorHTML);

                console.log("Bloc unité injecté.");
            }, 800); // 800ms pour être sûr que tout soit chargé
        },
    });

    return publicWidget.registry.UnitSelector;
});
