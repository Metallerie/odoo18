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

    line_ids = fields.One2many(
        "quick.quote.wizard.line",
        "wizard_id",
        string="Lignes",
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

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        sale_order_id = self.env.context.get("default_sale_order_id")
        if sale_order_id:
            order = self.env["sale.order"].browse(sale_order_id)
            line_commands = []

            for line in order.order_line.sorted(key=lambda l: (l.sequence, l.id)):
                if line.display_type:
                    continue

                line_commands.append((0, 0, {
                    "sale_line_id": line.id,
                    "name": (line.name or line.product_id.display_name or "").strip(),
                    "qty": line.product_uom_qty,
                    "uom_name": line.product_uom.name or "",
                    "price_unit": line.price_unit,
                    "subtotal": line.price_subtotal,
                    "en_stock": True,
                }))

            res["line_ids"] = line_commands
        return res

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
        "communication_text",
        "line_ids",
        "line_ids.en_stock",
        "line_ids.name",
        "line_ids.qty",
        "line_ids.uom_name",
        "line_ids.price_unit",
        "line_ids.subtotal",
        "line_ids.sale_line_id",
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
            wizard_line_map = {
                wizard_line.sale_line_id.id: wizard_line
                for wizard_line in wizard.line_ids
                if wizard_line.sale_line_id
            }

            has_out_of_stock = False
            pending_blank_line = False

            for line in lines:
                if line.display_type == "line_section":
                    if line.name:
                        if parts and parts[-1] != "":
                            parts.append("")
                        parts.append(line.name.strip())
                        parts.append("")
                    pending_blank_line = False
                    continue

                if line.display_type == "line_note":
                    if line.name:
                        parts.append(line.name.strip())
                    pending_blank_line = True
                    continue

                wizard_line = wizard_line_map.get(line.id)
                if not wizard_line:
                    continue

                if pending_blank_line and parts and parts[-1] != "":
                    parts.append("")

                label = wizard_line.name.strip()
                qty = wizard._format_quantity(wizard_line.qty)
                uom_name = (wizard_line.uom_name or "").strip()
                unit_price = wizard._format_amount(wizard_line.price_unit)
                subtotal = wizard._format_amount(wizard_line.subtotal)

                parts.append(f"{label} : {qty} {uom_name} x {unit_price} = {subtotal}")

                if wizard_line.en_stock:
                    parts.append("Disponible en stock")
                else:
                    parts.append("Hors stock")
                    has_out_of_stock = True

                pending_blank_line = False

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


class QuickQuoteWizardLine(models.TransientModel):
    _name = "quick.quote.wizard.line"
    _description = "Ligne assistant devis rapide"
    _order = "id"

    wizard_id = fields.Many2one(
        "quick.quote.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )

    sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Ligne de devis",
        readonly=True,
    )

    name = fields.Char(
        string="Produit",
        readonly=True,
    )

    qty = fields.Float(
        string="Quantité",
        readonly=True,
    )

    uom_name = fields.Char(
        string="UdM",
        readonly=True,
    )

    price_unit = fields.Float(
        string="Prix unitaire",
        readonly=True,
    )

    subtotal = fields.Float(
        string="Sous-total",
        readonly=True,
    )

    en_stock = fields.Boolean(
        string="En stock",
        default=True,
    )
