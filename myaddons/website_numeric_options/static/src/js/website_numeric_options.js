/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.WebsiteNumericOptions = publicWidget.Widget.extend({
    selector: ".oe_website_sale",

    events: {
        "input input": "_onInputChanged",
        "change input": "_onInputChanged",
        "change select": "_onInputChanged",
    },

    start() {
        this._super(...arguments);
        this._computeNumericOptions();
    },

    _parseNumber(value) {
        if (!value) {
            return 0;
        }
        const cleaned = String(value).replace(",", ".");
        const number = parseFloat(cleaned);
        return isNaN(number) ? 0 : number;
    },

    _formatNumber(value) {
        if (Number.isInteger(value)) {
            return String(value);
        }
        return String(Math.round(value * 10000) / 10000).replace(".", ",");
    },

    _findInputByLabel(labelText) {
        const labels = this.el.querySelectorAll("label, .css_attribute_color, strong, b");
        labelText = labelText.toLowerCase();

        for (const label of labels) {
            if ((label.textContent || "").toLowerCase().includes(labelText)) {
                const container = label.closest(".variant_attribute, .js_product, .mb-3, div");
                if (container) {
                    const input = container.querySelector("input[type='text'], input:not([type]), input.form-control");
                    if (input) {
                        return input;
                    }
                }
            }
        }

        const allInputs = this.el.querySelectorAll("input[type='text'], input:not([type]), input.form-control");
        for (const input of allInputs) {
            const placeholder = (input.placeholder || "").toLowerCase();
            if (placeholder.includes(labelText)) {
                return input;
            }
        }

        return null;
    },

    _getQuantityInput() {
        return this.el.querySelector("input[name='add_qty']");
    },

    _computeNumericOptions() {
        const cutQtyInput = this._findInputByLabel("nombre de coupes");
        const cutLengthInput = this._findInputByLabel("longueur de coupe");
        const computedInput = this._findInputByLabel("calcule quantité");

        if (!cutQtyInput || !cutLengthInput || !computedInput) {
            return;
        }

        const cutQty = this._parseNumber(cutQtyInput.value);
        const cutLength = this._parseNumber(cutLengthInput.value);

        if (!cutQty || !cutLength) {
            return;
        }

        const exactQty = cutQty * cutLength;
        const soldQty = Math.ceil(exactQty);

        computedInput.value = this._formatNumber(exactQty);
        computedInput.dispatchEvent(new Event("input", { bubbles: true }));
        computedInput.dispatchEvent(new Event("change", { bubbles: true }));

        const qtyInput = this._getQuantityInput();
        if (qtyInput) {
            qtyInput.value = this._formatNumber(soldQty);
            qtyInput.dispatchEvent(new Event("input", { bubbles: true }));
            qtyInput.dispatchEvent(new Event("change", { bubbles: true }));
        }
    },

    _onInputChanged() {
        window.clearTimeout(this.numericOptionsTimer);
        this.numericOptionsTimer = window.setTimeout(() => {
            this._computeNumericOptions();
        }, 100);
    },
});
