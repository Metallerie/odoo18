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
            this._formatCartNumericOptions();
            this._bindCartProtection();
            return;
        }

        this._initializeNumericFields();
        window.setTimeout(() => this._computeNumericOptions(), 300);
    },

    _isCartPage() {
        return window.location.pathname.includes("/shop/cart");
    },

    _normalize(text) {
        return (text || "")
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .trim();
    },

    _parseNumber(value) {
        if (!value) return 0;
        const number = parseFloat(String(value).replace(",", "."));
        return isNaN(number) ? 0 : number;
    },

    _formatInteger(value) {
        return String(Math.max(0, Math.floor(this._parseNumber(value))));
    },

    _formatDecimal(value) {
        return Math.max(0, this._parseNumber(value)).toFixed(2);
    },

    _getOptionBlocks() {
        return this.el.querySelectorAll("fieldset, .mb-3, .variant_attribute");
    },

    _findInputByBlockLabel(labels) {
        const wantedLabels = labels.map((label) => this._normalize(label));

        for (const block of this._getOptionBlocks()) {
            const text = this._normalize(block.innerText || "");

            if (wantedLabels.some((label) => text.includes(label))) {
                const input = block.querySelector("input[type='text'], input.form-control, input:not([type])");
                if (input) return input;
            }
        }

        return null;
    },

    _findInputByPlaceholder(labels) {
        const wantedLabels = labels.map((label) => this._normalize(label));
        const inputs = this.el.querySelectorAll("input[type='text'], input.form-control, input:not([type])");

        for (const input of inputs) {
            const placeholder = this._normalize(input.placeholder || "");

            if (wantedLabels.some((label) => placeholder.includes(label))) {
                return input;
            }
        }

        return null;
    },

    _getCutQtyInput() {
        return this._findInputByBlockLabel([
            "nombre de piece",
            "nombre de pièce",
            "nombre de pieces",
            "nombre de pièces",
            "nombre de coupe",
            "nombre de coupes",
        ]);
    },

    _getCutLengthInput() {
        return this._findInputByBlockLabel([
            "longueur de coupe",
        ]);
    },

    _getComputedInput() {
        // Important : on cherche d'abord par placeholder pour ne pas confondre avec "Nombre de pièce"
        return (
            this._findInputByPlaceholder([
                "longueur totale coupee",
                "longueur totale coupée",
            ]) ||
            this._findInputByBlockLabel([
                "calcule quantite",
                "calcule quantité",
                "calcul quantite",
                "calcul quantité",
            ])
        );
    },

    _getQuantityInput() {
        return this.el.querySelector("input[name='add_qty']");
    },

    _setValue(input, value, triggerEvents = true) {
        if (!input) return;
        if (String(input.value) === String(value)) return;

        input.value = value;

        if (triggerEvents) {
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.dispatchEvent(new Event("change", { bubbles: true }));
        }
    },

    _unlockInput(input) {
        if (!input) return;
        input.readOnly = false;
        input.disabled = false;
        input.classList.remove("bg-light");
    },

    _lockInput(input) {
        if (!input) return;
        input.readOnly = true;
        input.disabled = false;
        input.classList.add("bg-light");
    },

    _initializeNumericFields() {
        const cutQtyInput = this._getCutQtyInput();
        const cutLengthInput = this._getCutLengthInput();
        const computedInput = this._getComputedInput();
        const qtyInput = this._getQuantityInput();

        this._unlockInput(cutQtyInput);
        this._unlockInput(cutLengthInput);
        this._lockInput(computedInput);

        if (cutQtyInput && (!cutQtyInput.value || this._parseNumber(cutQtyInput.value) <= 0)) {
            this._setValue(cutQtyInput, "0", false);
        }

        if (cutLengthInput && (!cutLengthInput.value || this._parseNumber(cutLengthInput.value) <= 0)) {
            this._setValue(cutLengthInput, "0.00", false);
        }

        if (computedInput && !computedInput.value) {
            this._setValue(computedInput, "0.00", false);
        }

        if (qtyInput && this._parseNumber(qtyInput.value) <= 0) {
            this._setValue(qtyInput, "1", false);
        }
    },

    _computeNumericOptions() {
        if (this._isCartPage()) return;

        const cutQtyInput = this._getCutQtyInput();
        const cutLengthInput = this._getCutLengthInput();
        const computedInput = this._getComputedInput();
        const qtyInput = this._getQuantityInput();

        this._unlockInput(cutQtyInput);
        this._unlockInput(cutLengthInput);
        this._lockInput(computedInput);

        if (!cutQtyInput || !cutLengthInput || !computedInput) return;

        const cutQty = this._parseNumber(cutQtyInput.value);
        const cutLength = this._parseNumber(cutLengthInput.value);

        if (cutQty <= 0 || cutLength <= 0) {
            this._setValue(computedInput, "0.00", true);

            if (qtyInput) {
                this._setValue(qtyInput, "1", true);
            }

            return;
        }

        const exactQty = cutQty * cutLength;
        const soldQty = Math.ceil(exactQty);

        this._setValue(computedInput, this._formatDecimal(exactQty), true);

        // Quantité panier entière
        if (qtyInput) {
            this._setValue(qtyInput, String(soldQty), true);
        }
    },

    _onInputFocusOut(ev) {
        if (this._isCartPage()) return;

        const input = ev.target;
        const containerText = this._normalize(
            input.closest("fieldset, .mb-3, .variant_attribute")?.innerText || ""
        );

        if (
            containerText.includes("nombre de piece") ||
            containerText.includes("nombre de pieces") ||
            containerText.includes("nombre de coupe")
        ) {
            this._setValue(input, this._formatInteger(input.value), false);
        }

        if (containerText.includes("longueur de coupe")) {
            this._setValue(input, this._formatDecimal(input.value), false);
        }

        this._computeNumericOptions();
    },

    _onInputChanged() {
        if (this._isCartPage()) return;

        window.clearTimeout(this.numericOptionsTimer);
        this.numericOptionsTimer = window.setTimeout(() => {
            this._initializeNumericFields();
            this._computeNumericOptions();
        }, 200);
    },

    _getCartLines() {
        return this.el.querySelectorAll(
            "#cart_products .o_cart_product, #cart_products tr, .oe_cart .o_cart_product, .oe_cart tr"
        );
    },

    _formatCartNumericOptions() {},

    _bindCartProtection() {},
});
