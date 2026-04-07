from odoo import api, fields, models


class QuickQuoteWizard(models.TransientModel):
    _name = "quick.quote.wizard"
    _description = "Assistant devis rapide"

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Devis",
        required=True,
        readonly=True,
    )

    communication_text = fields.Text(
        string="Texte libre de communication"
    )

    generated_text = fields.Text(
        string="Texte à copier",
        compute="_compute_generated_text",
        readonly=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        related="sale_order_id.currency_id",
        store=False,
        readonly=True,
    )

    @api.depends(
        "sale_order_id",
        "sale_order_id.order_line.sequence",
        "sale_order_id.order_line.display_type",
        "sale_order_id.order_line.name",
        "sale_order_id.order_line.product_uom_qty",
        "sale_order_id.order_line.product_uom.name",
        "sale_order_id.order_line.price_unit",
        "sale_order_id.order_line.price_subtotal",
        "communication_text",
    )
    def _compute_generated_text(self):
        for wizard in self:
            parts = [
                "Bonjour,",
                "",
                "Voici votre devis :",
                "",
            ]

            order = wizard.sale_order_id
            lines = order.order_line.sorted(key=lambda l: (l.sequence, l.id))

            for line in lines:
                if line.display_type == "line_section":
                    if line.name:
                        parts.append(line.name)
                        parts.append("")
                    continue

                if line.display_type == "line_note":
                    if line.name:
                        parts.append(line.name)
                        parts.append("")
                    continue

                label = (line.name or line.product_id.display_name or "").strip()
                qty = wizard._format_quantity(line.product_uom_qty)
                uom_name = line.product_uom.name or ""
                unit_price = wizard._format_amount(line.price_unit)
                subtotal = wizard._format_amount(line.price_subtotal)

                parts.append(f"{label} : {qty} {uom_name} x {unit_price} = {subtotal}")
                parts.append("")

            parts.append(f"Total : {wizard._format_amount(order.amount_total)}")

            if wizard.communication_text:
                parts.append("")
                parts.append(wizard.communication_text.strip())

            parts.append("")
            parts.append("Retrait à l’atelier : La Métallerie, Corneilla-del-Vercol")
            parts.append("TEL: 0625159120")
            parts.append("TVA non applicable, art. 293 B du CGI")
            parts.append("Plus de prix sur le site internet metallerie.xyz ou La Métallerie – Corneilla-del-Vercol")

            wizard.generated_text = "\n".join(parts).strip()

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
