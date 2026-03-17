from odoo import api, fields, models


class QuickQuoteWizard(models.TransientModel):
    _name = "quick.quote.wizard"
    _description = "Assistant devis rapide"

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Devis",
        readonly=True,
    )

    pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Liste de prix",
        compute="_compute_pricelist_id",
        store=True,
    )

    line_ids = fields.One2many(
        "quick.quote.wizard.line",
        "wizard_id",
        string="Lignes",
    )

    note = fields.Text(string="Informations complémentaires")

    currency_id = fields.Many2one(
        "res.currency",
        string="Devise",
        compute="_compute_currency_id",
        store=True,
    )

    amount_total = fields.Monetary(
        string="Total",
        compute="_compute_amount_total",
        currency_field="currency_id",
    )

    generated_text = fields.Text(
        string="Texte à copier",
        compute="_compute_generated_text",
    )

    @api.depends("sale_order_id")
    def _compute_pricelist_id(self):
        for wizard in self:
            wizard.pricelist_id = wizard.sale_order_id.pricelist_id

    @api.depends("pricelist_id")
    def _compute_currency_id(self):
        for wizard in self:
            wizard.currency_id = wizard.pricelist_id.currency_id or wizard.env.company.currency_id

    @api.depends("line_ids.subtotal")
    def _compute_amount_total(self):
        for wizard in self:
            wizard.amount_total = sum(wizard.line_ids.mapped("subtotal"))

    @api.depends(
        "line_ids.sequence",
        "line_ids.product_id",
        "line_ids.name",
        "line_ids.quantity",
        "line_ids.uom_name",
        "line_ids.price_unit",
        "line_ids.subtotal",
        "line_ids.in_stock",
        "line_ids.cut_count",
        "line_ids.cut_length_mm",
        "line_ids.line_note",
        "note",
        "amount_total",
        "currency_id",
    )
    def _compute_generated_text(self):
        for wizard in self:
            parts = ["Bonjour", "", "Voici votre devis :", ""]

            ordered_lines = wizard.line_ids.sorted(key=lambda l: (l.sequence, l.id))
            for line in ordered_lines:
                if not line.product_id:
                    continue

                qty = wizard._format_quantity(line.quantity)
                unit_price = wizard._format_amount(line.price_unit)
                subtotal = wizard._format_amount(line.subtotal)
                label = line.name or line.product_id.display_name
                # Nettoyage du code produit [XXXX]
                if label.startswith("["):
                    label = label.split("] ", 1)[-1]
                uom_name = line.uom_name or "u"

                parts.append(f"{label} : {qty} {uom_name} x {unit_price} = {subtotal}")

                if line.in_stock:
                    parts.append("Disponible en stock")
                else:
                    parts.append("Produit non disponible en stock, merci de confirmer pour le prochain arrivage du mardi fin d'après-midi")

                if line.cut_count and line.cut_length_mm:
                    parts.append(f"Découpe : {int(line.cut_count)} x {int(line.cut_length_mm)} mm")

                if line.line_note:
                    parts.append(line.line_note)

                parts.append("")

            parts.append(f"Total : {wizard._format_amount(wizard.amount_total)}")

            if wizard.note:
                parts.append("")
                parts.append(wizard.note)

            parts.append("")
            parts.append("Retrait à l’atelier : La Métallerie, Corneilla-del-Vercol")
            parts.append("TVA non applicable, art. 293 B du CGI")
            parts.append("Plus de prix sur le site metallerie.xyz")

            wizard.generated_text = "\n".join([p for p in parts if p is not None]).strip()

    def _format_amount(self, amount):
        self.ensure_one()
        currency_symbol = self.currency_id.symbol or "€"
        value = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", " ")
        if self.currency_id.position == "before":
            return f"{currency_symbol}{value}"
        return f"{value} {currency_symbol}"

    def _format_quantity(self, qty):
        value = f"{qty:g}"
        return value.replace(".", ",")
