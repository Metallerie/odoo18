/* Copyright 2019 Sergio Teruel
 * Copyright 2025 Carlos Lopez - Tecnativa
 * DEBUG Franck
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). */

import "@website_sale/js/website_sale";
import VariantMixin from "@website_sale/js/sale_variant_mixin";
import publicWidget from "@web/legacy/js/public/public_widget";

/* ============================
 * GLOBAL AJAX DEBUG
 * ============================ */
(function () {
    const _ajax = jQuery.ajax;
    jQuery.ajax = function (options) {
        try {
            const url = typeof options === "string" ? options : options.url;
            if (url && (url.includes("/shop/cart/update_json") || url.includes("/shop/cart/update"))) {
                console.log("[WSU][AJAX] OUT →", url, {
                    type: options.type,
                    method: options.method,
                    data: options.data,
                });
            }
        } catch (e) {
            console.warn("[WSU][AJAX] hook error", e);
        }
        return _ajax.apply(this, arguments).then((res) => {
            try {
                const url = typeof options === "string" ? options : options.url;
                if (url && (url.includes("/shop/cart/update_json") || url.includes("/shop/cart/update"))) {
                    console.log("[WSU][AJAX] IN  ←", url, res);
                }
            } catch (e) {
                console.warn("[WSU][AJAX] hook response error", e);
            }
            return res;
        });
    };
})();

/* ============================
 * PRODUCT PAGE
 * ============================ */
publicWidget.registry.sale_secondary_unit = publicWidget.Widget.extend(VariantMixin, {
    selector: ".secondary-unit",

    init: function (parent, editableMode) {
        this._super.apply(this, arguments);
        this.$secondary_uom = null;
        this.$secondary_uom_qty = null;
        this.$product_qty = null;
        this.secondary_uom_qty = null;
        this.secondary_uom_factor = null;
        this.product_uom_factor = null;
        this.product_qty = null;
    },

    start: function () {
        const _this = this;
        this.$secondary_uom = $("#secondary_uom");
        this.$secondary_uom_qty = $(".secondary-quantity");
        this.$product_qty = $(".quantity");

        console.log("[WSU][PDP] start()", {
            has_secondary_uom: this.$secondary_uom.length,
            has_secondary_qty: this.$secondary_uom_qty.length,
            has_product_qty: this.$product_qty.length,
        });

        this._setValues();

        this.$target.on("change", ".secondary-quantity", this._onChangeSecondaryUom.bind(this));
        this.$target.on("change", "#secondary_uom", this._onChangeSecondaryUom.bind(this));
        this.$product_qty.on("change", null, this._onChangeProductQty.bind(this));

        return this._super.apply(this, arguments).then(function () {
            console.log("[WSU][PDP] initial _onChangeSecondaryUom()");
            _this._onChangeSecondaryUom();
        });
    },

    _setValues: function () {
        this.secondary_uom_qty = Number(this.$target.find(".secondary-quantity").val());
        this.secondary_uom_factor = Number($("option:selected", this.$secondary_uom).data("secondary-uom-factor"));
        this.product_uom_factor = Number($("option:selected", this.$secondary_uom).data("product-uom-factor"));
        this.product_qty = Number($(".quantity").val());

        console.log("[WSU][PDP] _setValues()", {
            secondary_uom_qty: this.secondary_uom_qty,
            secondary_uom_factor: this.secondary_uom_factor,
            product_uom_factor: this.product_uom_factor,
            product_qty: this.product_qty,
            secondary_uom_id: this.$secondary_uom.val(),
        });
    },

    _onChangeSecondaryUom: function (ev) {
        if (!ev) {
            ev = jQuery.Event("fakeEvent");
            ev.currentTarget = $(".form-control.quantity");
        }
        console.log("[WSU][PDP] _onChangeSecondaryUom()", { evType: ev.type });

        this._setValues();
        const factor = this.secondary_uom_factor * this.product_uom_factor;
        const newQty = this.secondary_uom_qty * factor;

        console.log("[WSU][PDP] secondary → primary", { factor, newQty });

        this.$product_qty.val(newQty);
        this.onChangeAddQuantity(ev);

        console.log("[WSU][PDP] after onChangeAddQuantity()", {
            product_qty_dom: this.$product_qty.val(),
        });
    },

    _onChangeProductQty: function () {
        this._setValues();
        const factor = this.secondary_uom_factor * this.product_uom_factor;
        const newSecondaryQty = this.product_qty / factor;

        console.log("[WSU][PDP] primary → secondary", { factor, newSecondaryQty });

        this.$secondary_uom_qty.val(newSecondaryQty);
    },
});

/* ============================
 * CART
 * ============================ */
publicWidget.registry.sale_secondary_unit_cart = publicWidget.Widget.extend({
    selector: ".oe_cart",

    init: function (parent, editableMode) {
        this._super.apply(this, arguments);
        this.$product_qty = null;
        this.secondary_uom_qty = null;
        this.secondary_uom_factor = null;
        this.product_uom_factor = null;
        this.product_qty = null;
    },

    start: function () {
        console.log("[WSU][CART] start()");

        // log ANY change on primary qty inputs too
        this.$target.on("change", "input.quantity[data-line-id]", (ev) => {
            console.log("[WSU][CART] primary qty changed", {
                line_id: ev.currentTarget.dataset.lineId,
                value: ev.currentTarget.value,
            });
        });

        this.$target.on("change", "input.js_secondary_quantity[data-line-id]", (ev) => {
            console.log("[WSU][CART] secondary qty changed", {
                line_id: ev.currentTarget.dataset.lineId,
                value: ev.currentTarget.value,
                dataset: { ...ev.currentTarget.dataset },
            });
            this._onChangeSecondaryUom(ev.currentTarget);
        });
    },

    _setValues: function (order_line) {
        this.$product_qty = this.$target.find(".quantity[data-line-id=" + order_line.dataset.lineId + "]");
        this.secondary_uom_qty = Number(order_line.value);
        this.secondary_uom_factor = Number(order_line.dataset.secondaryUomFactor);
        this.product_uom_factor = Number(order_line.dataset.productUomFactor);
        this.product_qty = Number(this.$product_qty.val());

        console.log("[WSU][CART] _setValues()", {
            line_id: order_line.dataset.lineId,
            secondary_uom_qty: this.secondary_uom_qty,
            secondary_uom_factor: this.secondary_uom_factor,
            product_uom_factor: this.product_uom_factor,
            primary_qty_before: this.product_qty,
        });
    },

    _onChangeSecondaryUom: function (order_line) {
        this._setValues(order_line);

        const factor = this.secondary_uom_factor * this.product_uom_factor;
        const newQty = this.secondary_uom_qty * factor;

        console.log("[WSU][CART] secondary → primary", {
            factor,
            newQty,
        });

        this.$product_qty.val(newQty);

        console.log("[WSU][CART] trigger change on primary qty", {
            line_id: order_line.dataset.lineId,
            primary_qty_after: this.$product_qty.val(),
        });

        this.$product_qty.trigger("change");
    },
});

publicWidget.registry.WebsiteSale.include({
    _onChangeCombination: function (ev, $parent, combination) {
        console.log("[WSU] _onChangeCombination()", combination);
        const quantity = $parent.find(".css_quantity:not(.secondary_qty)");
        const res = this._super(...arguments);
        if (combination.has_secondary_uom) {
            quantity.removeClass("d-inline-flex").addClass("d-none");
        } else {
            quantity.removeClass("d-none").addClass("d-inline-flex");
        }
        return res;
    },

    _submitForm: function () {
        console.log("[WSU] _submitForm BEFORE", this.rootProduct);

        if (!("secondary_uom_id" in this.rootProduct) && $(this.$target).find("#secondary_uom").length) {
            this.rootProduct.secondary_uom_id = $(this.$target).find("#secondary_uom").val();
            this.rootProduct.secondary_uom_qty = $(this.$target).find(".secondary-quantity").val();
        }

        console.log("[WSU] _submitForm AFTER", this.rootProduct);
        return this._super.apply(this, arguments);
    },
});
