/* ocaaddons/website_sale_secondary_unit/static/src/js/website_sale_secondary_unit.esm.js */
import "@website_sale/js/website_sale";
import VariantMixin from "@website_sale/js/sale_variant_mixin";
import publicWidget from "@web/legacy/js/public/public_widget";

const parseFRFloat = (v) => {
    if (v === undefined || v === null) return 0;
    if (typeof v === "number") return v;
    const s = String(v).trim().replace(/\s/g, "").replace(",", ".");
    const n = parseFloat(s);
    return Number.isFinite(n) ? n : 0;
};

publicWidget.registry.sale_secondary_unit = publicWidget.Widget.extend(VariantMixin, {
    selector: ".secondary-unit",
    start: function () {
        this.$qty = this.$target.find("input[name='add_secondary_qty']");
        this.$estimate = this.$target.find(".js_primary_estimate");
        this.$qty.on("change keyup", this._refreshEstimate.bind(this));
        this._refreshEstimate();
        return this._super.apply(this, arguments);
    },
    _refreshEstimate: function () {
        // On récupère le facteur via rootProduct (combination_info) si dispo,
        // sinon on laisse 0 (le serveur restera la vérité)
        const secQty = parseFRFloat(this.$qty.val());
        const factor = parseFRFloat(this.rootProduct?.sale_secondary_factor || 0);
        const primary = secQty * factor;
        if (this.$estimate.length) {
            this.$estimate.text(primary ? primary.toFixed(3) : "0");
        }
    },
});

publicWidget.registry.WebsiteSale.include({
    _onChangeCombination: function (ev, $parent, combination) {
        const res = this._super(...arguments);
        // injecter le facteur dans rootProduct pour l'estimation
        if (combination && combination.sale_secondary_factor) {
            this.rootProduct.sale_secondary_factor = combination.sale_secondary_factor;
        }
        return res;
    },
});
