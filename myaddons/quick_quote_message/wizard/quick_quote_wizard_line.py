from odoo import api, fields, models


class QuickQuoteWizardLine(models.TransientModel):
    _name = "quick.quote.wizard.line"
    _description = "Ligne assistant devis rapide"
    _order = "sequence, id"

    wizard_id = fields.Many2one(
        "quick.quote.wizard",
        string="Assistant",
        required=True,
        ondelete="cascade",
    )

    sequence = fields.Integer(default=10)

    product_id = fields.Many2one(
        "product.product",
        string="Produit",
        required=True,
    )

    name = fields.Char(string="Libellé")

    quantity = fields.Float(
        string="Quantité",
        default=1.0,
        required=True,
    )

    uom_name = fields.Char(
        string="Unité",
        compute="_compute_uom_name",
        store=True,
    )

    price_unit = fields.Monetary(
        string="Prix unitaire",
        currency_field="currency_id",
        required=True,
    )

    subtotal = fields.Monetary(
        string="Sous-total",
        compute="_compute_subtotal",
        currency_field="currency_id",
        store=True,
    )

    cut_count = fields.Integer(
        string="Nb coupes",
        default=0,
    )

    cut_length_mm = fields.Integer(
        string="Longueur mm",
        default=0,
    )

    line_note = fields.Text(string="Ligne libre")

    currency_id = fields.Many2one(
        related="wizard_id.currency_id",
        store=True,
    )

    @api.depends("product_id")
    def _compute_uom_name(self):
        for line in self:
            if line.product_id and line.product_id.uom_id:
                line.uom_name = line.product_id.uom_id.name
            else:
                line.uom_name = ""

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if not line.product_id:
                continue
            line.name = line.product_id.display_name
            line.price_unit = line.product_id.lst_price
            line.uom_name = line.product_id.uom_id.name or ""
