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
        setTimeout(() => this._computeNumericOptions(), 300);
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

    _findInputByLabels(labels) {
        const wantedLabels = labels.map((l) => this._normalize(l));

        const blocks = this.el.querySelectorAll("fieldset, .mb-3, .variant_attribute, .js_product, div");

        for (const block of blocks) {
            const text = this._normalize(block.innerText || "");

            if (wantedLabels.some((label) => text.includes(label))) {
                const input = block.querySelector("input[type='text'], input.form-control, input:not([type])");
                if (input) return input;
            }
        }

        const inputs = this.el.querySelectorAll("input[type='text'], input.form-control, input:not([type])");

        for (const input of inputs) {
            const placeholder = this._normalize(input.placeholder || "");
            const name = this._normalize(input.name || "");

            if (wantedLabels.some((label) => placeholder.includes(label) || name.includes(label))) {
                return input;
            }
        }

        return null;
    },

    _getCutQtyInput() {
        return this._findInputByLabels([
            "nombre de piece",
            "nombre de pièce",
            "nombre de pieces",
            "nombre de pièces",
            "nombre de coupe",
            "nombre de coupes",
        ]);
    },

    _getCutLengthInput() {
        return this._findInputByLabels([
            "longueur de coupe",
            "longueur coupe",
        ]);
    },

    _getComputedInput() {
        return this._findInputByLabels([
            "calcule quantite",
            "calcul quantité",
            "calcule quantité",
            "quantite calculee",
            "quantité calculée",
        ]);
    },

    _getQuantityInput() {
        return this.el.querySelector("input[name='add_qty']");
    },

    _updateInputIfChanged(input, newValue, triggerEvents = true) {
        if (!input) return;

        if (String(input.value) === String(newValue)) return;

        input.value = newValue;

        if (triggerEvents) {
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.dispatchEvent(new Event("change", { bubbles: true }));
        }
    },

    _initializeNumericFields() {
        const cutQtyInput = this._getCutQtyInput();
        const cutLengthInput = this._getCutLengthInput();
        const computedInput = this._getComputedInput();

        if (cutQtyInput && !cutQtyInput.value) {
            this._updateInputIfChanged(cutQtyInput, "0", false);
        }

        if (cutLengthInput && !cutLengthInput.value) {
            this._updateInputIfChanged(cutLengthInput, "0.00", false);
        }

        if (computedInput) {
            computedInput.readOnly = true;
            computedInput.classList.add("bg-light");

            if (!computedInput.value || this._parseNumber(computedInput.value) === 0) {
                this._updateInputIfChanged(computedInput, "0.00", false);
            }
        }
    },

    _computeNumericOptions() {
        if (this._isCartPage()) return;

        const cutQtyInput = this._getCutQtyInput();
        const cutLengthInput = this._getCutLengthInput();
        const computedInput = this._getComputedInput();
        const qtyInput = this._getQuantityInput();

        if (!cutQtyInput || !cutLengthInput || !computedInput) return;

        const cutQty = this._parseNumber(cutQtyInput.value);
        const cutLength = this._parseNumber(cutLengthInput.value);

        if (cutQty <= 0 || cutLength <= 0) {
            this._updateInputIfChanged(computedInput, "0.00", true);
            return;
        }

        const exactQty = cutQty * cutLength;
        const soldQty = Math.ceil(exactQty);

        this._updateInputIfChanged(computedInput, this._formatDecimal(exactQty), true);

        if (qtyInput) {
            this._updateInputIfChanged(qtyInput, String(soldQty), true);
        }
    },

    _getCartLines() {
        return this.el.querySelectorAll(
            "#cart_products .o_cart_product, #cart_products tr, .oe_cart .o_cart_product, .oe_cart tr"
        );
    },

    _formatCartNumericOptions() {
        const cartLines = this._getCartLines();

        for (const line of cartLines) {
            const lineText = line.innerText || "";

            if (!this._normalize(lineText).includes("longueur de coupe")) {
                continue;
            }

            const quantityMatch = lineText.match(
                /Nombre de pi[eè]ce[^:]*:\s*(?:Quantit[eé]\s*:\s*)?([0-9]+(?:[,.][0-9]+)?)/i
            );

            const lengthMatch = lineText.match(
                /Longueur de coupe[^:]*:\s*(?:Dimension\s*:\s*)?([0-9]+(?:[,.][0-9]+)?)/i
            );

            if (!quantityMatch || !lengthMatch) continue;

            const cutQty = this._parseNumber(quantityMatch[1]);
            const cutLength = this._parseNumber(lengthMatch[1]);
            const totalLength = cutQty * cutLength;

            if (totalLength <= 0) continue;

            const optionElements = line.querySelectorAll("small, span, div, li");

            for (const el of optionElements) {
                const content = this._normalize(el.textContent || "");

                if (content.startsWith("calcule quantite") || content.startsWith("calcul quantite")) {
                    el.textContent = `Calcule quantité: Longueur totale coupée: ${this._formatDecimal(totalLength)}`;
                    break;
                }
            }
        }
    },

    _bindCartProtection() {
        const cartLines = this._getCartLines();

        for (const line of cartLines) {
            const text = this._normalize(line.innerText || "");

            if (!text.includes("longueur de coupe")) {
                continue;
            }

            const plusButtons = line.querySelectorAll(".js_add, button:has(.fa-plus)");
            const minusButtons = line.querySelectorAll(".js_subtract, button:has(.fa-minus)");
            const qtyInput = line.querySelector("input[name='add_qty'], input.js_quantity");

            for (const plus of plusButtons) {
                plus.addEventListener("click", (ev) => {
                    ev.preventDefault();
                    ev.stopPropagation();
                    this._showCartWarning(line);
                });
            }

            for (const minus of minusButtons) {
                minus.addEventListener("click", (ev) => {
                    if (!qtyInput) return;

                    const currentQty = this._parseNumber(qtyInput.value);

                    if (currentQty <= 1) {
                        return;
                    }

                    ev.preventDefault();
                    ev.stopPropagation();
                    this._showCartWarning(line);
                });
            }

            if (qtyInput) {
                const originalValue = qtyInput.value;

                qtyInput.addEventListener("input", () => {
                    if (String(qtyInput.value).trim() === "0") {
                        return;
                    }

                    this._showCartWarning(line);
                    qtyInput.value = originalValue;
                });
            }
        }
    },

    _showCartWarning(line) {
        if (line.querySelector(".o_cart_warning_numeric")) return;

        const warning = document.createElement("div");
        warning.className = "text-danger mt-2 o_cart_warning_numeric";
        warning.style.fontSize = "0.9em";
        warning.innerHTML = `
            ⚠️ Quantité calculée automatiquement.<br>
            Pour modifier, mettez la quantité à 0 puis recommencez depuis la fiche produit.
        `;

        const target = line.querySelector(".td-product_name, .o_cart_product_name, td, div") || line;
        target.appendChild(warning);

        window.setTimeout(() => {
            warning.remove();
        }, 4000);
    },

    _onInputFocusOut(ev) {
        if (this._isCartPage()) return;

        const input = ev.target;
        const containerText = this._normalize(
            input.closest("fieldset, .mb-3, .variant_attribute, div")?.innerText || ""
        );

        if (
            containerText.includes("nombre de piece") ||
            containerText.includes("nombre de pieces") ||
            containerText.includes("nombre de coupe")
        ) {
            this._updateInputIfChanged(input, this._formatInteger(input.value), false);
        }

        if (containerText.includes("longueur de coupe")) {
            this._updateInputIfChanged(input, this._formatDecimal(input.value), false);
        }

        this._computeNumericOptions();
    },

    _onInputChanged() {
        if (this._isCartPage()) return;

        window.clearTimeout(this.numericOptionsTimer);
        this.numericOptionsTimer = window.setTimeout(() => {
            this._computeNumericOptions();
        }, 200);
    },
});
