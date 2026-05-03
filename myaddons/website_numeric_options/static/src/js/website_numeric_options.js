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

        if (this._isCartPage()) {
            return;
        }

        this._initializeNumericFields();
        this._computeNumericOptions();
    },

    _isCartPage() {
        return window.location.pathname.includes("/shop/cart");
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

    _updateInputIfChanged(input, newValue, triggerEvents = true) {
        if (!input) {
            return;
        }

        if (String(input.value) === String(newValue)) {
            return;
        }

        input.value = newValue;

        if (triggerEvents) {
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.dispatchEvent(new Event("change", { bubbles: true }));
        }
    },

    _initializeNumericFields() {
        const cutQtyInput = this._findInputByLabel("nombre de coupes");
        const cutLengthInput = this._findInputByLabel("longueur de coupe");
        const computedInput = this._findInputByLabel("calcule quantité");

        if (cutQtyInput && !cutQtyInput.value) {
            this._updateInputIfChanged(cutQtyInput, "0", false);
        }

        if (cutLengthInput && !cutLengthInput.value) {
            this._updateInputIfChanged(cutLengthInput, "0.00", false);
        }

        if (computedInput) {
            computedInput.readOnly = true;
            if (!computedInput.value) {
                this._updateInputIfChanged(computedInput, "0.00", false);
            }
        }
    },

    _computeNumericOptions() {
        if (this._isCartPage()) {
            return;
        }

        const cutQtyInput = this._findInputByLabel("nombre de coupes");
        const cutLengthInput = this._findInputByLabel("longueur de coupe");
        const computedInput = this._findInputByLabel("calcule quantité");

        if (!cutQtyInput || !cutLengthInput || !computedInput) {
            return;
        }

        const cutQty = this._parseNumber(cutQtyInput.value);
        const cutLength = this._parseNumber(cutLengthInput.value);

        if (cutQty <= 0 || cutLength <= 0) {
            return;
        }

        const exactQty = cutQty * cutLength;
        const soldQty = Math.ceil(exactQty);

        this._updateInputIfChanged(computedInput, this._formatDecimal(exactQty), true);

        const qtyInput = this._getQuantityInput();
        if (qtyInput) {
            this._updateInputIfChanged(qtyInput, String(soldQty), true);
        }
    },

    _onInputFocusOut(ev) {
        if (this._isCartPage()) {
            return;
        }

        const input = ev.target;
        const containerText = (input.closest(".mb-3, .variant_attribute, div")?.innerText || "").toLowerCase();

        if (containerText.includes("nombre de coupes")) {
            this._updateInputIfChanged(input, this._formatInteger(input.value), false);
        }

        if (containerText.includes("longueur de coupe")) {
            this._updateInputIfChanged(input, this._formatDecimal(input.value), false);
        }

        this._computeNumericOptions();
    },

    _onInputChanged() {
        if (this._isCartPage()) {
            return;
        }

        window.clearTimeout(this.numericOptionsTimer);
        this.numericOptionsTimer = window.setTimeout(() => {
            this._computeNumericOptions();
        }, 300);
    },
});
