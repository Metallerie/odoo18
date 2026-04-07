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
            pending_extra_lines = []

            for line in lines:
                if line.display_type == "line_section":
                    if line.name:
                        if parts and parts[-1] != "":
                            parts.append("")
                        parts.append(line.name.strip())
                        parts.append("")
                    pending_extra_lines = []
                    continue

                if line.display_type == "line_note":
                    if line.name:
                        parts.append(line.name.strip())
                    continue

                product_label, inline_notes = wizard._split_product_and_notes(line)

                qty = wizard._format_quantity(line.product_uom_qty)
                uom_name = (line.product_uom.name or "").strip()
                unit_price = wizard._format_amount(line.price_unit)
                subtotal = wizard._format_amount(line.price_subtotal)

                if parts and parts[-1] != "":
                    parts.append("")

                parts.append(f"{product_label} : {qty} {uom_name} x {unit_price} = {subtotal}")

                if line.quick_quote_in_stock:
                    parts.append("Disponible en stock")
                else:
                    parts.append("Hors stock")
                    has_out_of_stock = True

                for extra_line in inline_notes:
                    parts.append(extra_line)

            if parts and parts[-1] != "":
                parts.append("")

            parts.append(f"Total : {wizard._format_amount(order.amount_total)}")

            if wizard.communication_text:
                parts.append("")
                parts.append(wizard.communication_text.strip())

            if has_out_of_stock:
                parts.append("")
                parts.append("Pour les commandes hors stock, veuillez passer commande en ligne. Confirmation avant lundi pour l’arrivage de mardi.")
                parts.append("https://www.metallerie.xyz/shop ou La Métallerie – Corneilla-del-Vercol.")

            parts.append("")
            parts.append("Retrait à l’atelier : La Métallerie, Corneilla-del-Vercol")
            parts.append("TEL: 0625159120")
            parts.append("TVA non applicable, art. 293 B du CGI")
            parts.append("Plus de prix sur le site internet metallerie.xyz ou La Métallerie – Corneilla-del-Vercol")

            wizard.generated_text = "\n".join(parts).strip()

    def _split_product_and_notes(self, line):
        """
        Retourne :
        - le libellé produit propre
        - les lignes complémentaires éventuelles venant du champ name
        """
        raw_name = (line.name or "").strip()
        raw_lines = [l.strip() for l in raw_name.splitlines() if l.strip()]

        product_label = (line.product_id.display_name or "").strip()

        # Si display_name est vide, on prend la première ligne comme libellé
        if not product_label and raw_lines:
            product_label = raw_lines[0]

        inline_notes = []

        # On retire la première ligne si elle correspond au produit
        if raw_lines:
            first_line = raw_lines[0]
            if product_label and first_line == product_label:
                inline_notes = raw_lines[1:]
            elif product_label:
                inline_notes = raw_lines
            else:
                product_label = first_line
                inline_notes = raw_lines[1:]

        return product_label, inline_notes

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
