/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.WebsiteNumericOptions = publicWidget.Widget.extend({
    selector: ".oe_website_sale",

    events: {
        "input input": "_onInputChanged",
        "change input": "_onInputChanged",
        "change select": "_onInputChanged",
        "focusout input": "_onInputFocusOut",
    },

    start() {
        this._super(...arguments);
        this._initializeNumericFields();
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

    _formatInteger(value) {
        const number = this._parseNumber(value);
        return String(Math.max(0, Math.floor(number)));
    },

    _formatDecimal(value) {
        const number = this._parseNumber(value);
        return Math.max(0, number).toFixed(2);
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

    _initializeNumericFields() {
        const cutQtyInput = this._findInputByLabel("nombre de coupes");
        const cutLengthInput = this._findInputByLabel("longueur de coupe");
        const computedInput = this._findInputByLabel("calcule quantité");

        if (cutQtyInput && !cutQtyInput.value) {
            cutQtyInput.value = "0";
        }

        if (cutLengthInput && !cutLengthInput.value) {
            cutLengthInput.value = "0.00";
        }

        if (computedInput) {
            computedInput.readOnly = true;
            if (!computedInput.value) {
                computedInput.value = "0.00";
            }
        }
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

        const exactQty = cutQty * cutLength;
        const soldQty = Math.ceil(exactQty);

        computedInput.value = this._formatDecimal(exactQty);
        computedInput.dispatchEvent(new Event("input", { bubbles: true }));
        computedInput.dispatchEvent(new Event("change", { bubbles: true }));

        const qtyInput = this._getQuantityInput();
        if (qtyInput) {
            qtyInput.value = String(soldQty);
            qtyInput.dispatchEvent(new Event("input", { bubbles: true }));
            qtyInput.dispatchEvent(new Event("change", { bubbles: true }));
        }
    },

    _onInputFocusOut(ev) {
        const input = ev.target;
        const containerText = (input.closest(".mb-3, .variant_attribute, div")?.innerText || "").toLowerCase();

        if (containerText.includes("nombre de coupes")) {
            input.value = this._formatInteger(input.value);
        }

        if (containerText.includes("longueur de coupe")) {
            input.value = this._formatDecimal(input.value);
        }

        this._computeNumericOptions();
    },

    _onInputChanged() {
        window.clearTimeout(this.numericOptionsTimer);
        this.numericOptionsTimer = window.setTimeout(() => {
            this._computeNumericOptions();
        }, 100);
    },
});
