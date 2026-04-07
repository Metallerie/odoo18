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
        "sale_order_id.amount_total",
        "sale_order_id.order_line.sequence",
        "sale_order_id.order_line.display_type",
        "sale_order_id.order_line.name",
        "sale_order_id.order_line.product_uom_qty",
        "sale_order_id.order_line.product_uom.name",
        "sale_order_id.order_line.price_unit",
        "sale_order_id.order_line.price_subtotal",
        "sale_order_id.order_line.quick_quote_in_stock",
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
            has_out_of_stock = False
            previous_was_product = False

            for line in lines:
                if line.display_type == "line_section":
                    if line.name:
                        if parts and parts[-1] != "":
                            parts.append("")
                        parts.append(line.name.strip())
                        parts.append("")
                    previous_was_product = False
                    continue

                if line.display_type == "line_note":
                    if line.name:
                        parts.append(line.name.strip())
                    previous_was_product = False
                    continue

                if previous_was_product and parts and parts[-1] != "":
                    parts.append("")

                label = (line.name or line.product_id.display_name or "").strip()
                qty = wizard._format_quantity(line.product_uom_qty)
                uom_name = (line.product_uom.name or "").strip()
                unit_price = wizard._format_amount(line.price_unit)
                subtotal = wizard._format_amount(line.price_subtotal)

                parts.append(f"{label} : {qty} {uom_name} x {unit_price} = {subtotal}")

                if line.quick_quote_in_stock:
                    parts.append("Disponible en stock")
                else:
                    parts.append("Hors stock")
                    has_out_of_stock = True

                previous_was_product = True

            if parts and parts[-1] != "":
                parts.append("")

            parts.append(f"Total : {wizard._format_amount(order.amount_total)}")

            if wizard.communication_text:
                parts.append("")
                parts.append(wizard.communication_text.strip())

            if has_out_of_stock:
                parts.append("")
                parts.append("Veuillez passer commande en ligne. Confirmation avant lundi pour l’arrivage de mardi.")

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
