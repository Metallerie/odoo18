from odoo import api, fields, models
from odoo.exceptions import UserError


class QuickQuoteWizard(models.TransientModel):
    _name = "quick.quote.wizard"
    _description = "Assistant devis rapide"

    line_ids = fields.One2many(
        "quick.quote.wizard.line",
        "wizard_id",
        string="Lignes",
    )
    note = fields.Text(string="Informations de fin")
    amount_total = fields.Monetary(
        string="Total",
        compute="_compute_amount_total",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Devise",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    generated_text = fields.Text(
        string="Texte à copier",
        compute="_compute_generated_text",
    )

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
        "line_ids.line_note",
        "amount_total",
        "note",
        "currency_id",
    )
    def _compute_generated_text(self):
        for wizard in self:
            parts = ["Bonjour", "", "Voici votre devis :", ""]

            ordered_lines = wizard.line_ids.sorted(key=lambda l: (l.sequence, l.id))
            for line in ordered_lines:
                if not line.product_id:
                    continue

                qty = ("%g" % line.quantity).replace(".", ",")
                unit_price = wizard._format_amount(line.price_unit)
                subtotal = wizard._format_amount(line.subtotal)
                label = line.name or line.product_id.display_name
                uom_name = line.uom_name or "u"

                parts.append(
                    f"{label} : {qty} {uom_name} x {unit_price} = {subtotal}"
                )
                if line.line_note:
                    parts.append(line.line_note)
                parts.append("")

            parts.append(f"Total : {wizard._format_amount(wizard.amount_total)}")
            parts.append("")
            parts.append("TVA non applicable, art. 293 B du CGI")
        return {"type": "ir.actions.act_window_close"}
