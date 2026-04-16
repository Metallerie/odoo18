# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PurchaseFrequencyReport(models.TransientModel):
    _name = "purchase.frequency.report"
    _description = "Purchase Frequency Report"

    month_count = fields.Integer(
        string="Nombre de mois",
        required=True,
        default=6,
    )
    categ_id = fields.Many2one(
        "product.category",
        string="Catégorie produit",
    )
    line_ids = fields.One2many(
        "purchase.frequency.report.line",
        "wizard_id",
        string="Lignes",
        readonly=True,
    )

    @api.constrains("month_count")
    def _check_month_count(self):
        for rec in self:
            if rec.month_count <= 0:
                raise ValidationError(_("Le nombre de mois doit être supérieur à 0."))

    def action_generate_report(self):
        self.ensure_one()
        self.line_ids.unlink()

        date_from = fields.Datetime.now() - timedelta(days=self.month_count * 30)

        domain = [
            ("move_id.move_type", "=", "in_invoice"),
            ("move_id.state", "=", "posted"),
            ("move_id.invoice_date", ">=", fields.Date.to_string(date_from.date())),
            ("product_id", "!=", False),
            ("display_type", "=", "product"),
        ]

        if self.categ_id:
            domain.append(("product_id.categ_id", "child_of", self.categ_id.id))

        invoice_lines = self.env["account.move.line"].search(
            domain,
            order="product_id, move_id.invoice_date",
        )

        grouped_data = {}

        for line in invoice_lines:
            product = line.product_id
            if not product:
                continue

            product_id = product.id
            if product_id not in grouped_data:
                grouped_data[product_id] = {
                    "wizard_id": self.id,
                    "product_id": product.id,
                    "default_code": product.default_code or "",
                    "name": product.display_name,
                    "categ_id": product.categ_id.id,
                    "purchase_count": 0,
                    "total_qty": 0.0,
                    "last_purchase_date": False,
                }

            grouped_data[product_id]["purchase_count"] += 1
            grouped_data[product_id]["total_qty"] += line.quantity

            invoice_date = line.move_id.invoice_date
            last_date = grouped_data[product_id]["last_purchase_date"]
            if invoice_date and (not last_date or invoice_date > last_date):
                grouped_data[product_id]["last_purchase_date"] = invoice_date

        line_values = []
        today = fields.Date.today()

        for values in grouped_data.values():
            purchase_count = values["purchase_count"]
            total_qty = values["total_qty"]
            avg_qty = total_qty / purchase_count if purchase_count else 0.0

            last_purchase_date = values["last_purchase_date"]
            days_since_last = 0
            if last_purchase_date:
                days_since_last = (today - last_purchase_date).days

            values.update({
                "avg_qty": avg_qty,
                "days_since_last_purchase": days_since_last,
            })
            line_values.append(values)

        if line_values:
            self.env["purchase.frequency.report.line"].create(line_values)

        return {
            "type": "ir.actions.act_window",
            "name": _("Fréquence d'achat"),
            "res_model": "purchase.frequency.report",
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }


class PurchaseFrequencyReportLine(models.TransientModel):
    _name = "purchase.frequency.report.line"
    _description = "Purchase Frequency Report Line"
    _order = "purchase_count desc, total_qty desc, name asc"

    wizard_id = fields.Many2one(
        "purchase.frequency.report",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Produit",
        readonly=True,
    )
    default_code = fields.Char(
        string="Référence",
        readonly=True,
    )
    name = fields.Char(
        string="Désignation",
        readonly=True,
    )
    categ_id = fields.Many2one(
        "product.category",
        string="Catégorie",
        readonly=True,
    )
    purchase_count = fields.Integer(
        string="Nombre de lignes",
        readonly=True,
    )
    total_qty = fields.Float(
        string="Quantité totale achetée",
        readonly=True,
    )
    avg_qty = fields.Float(
        string="Qté moyenne / ligne",
        readonly=True,
    )
    last_purchase_date = fields.Date(
        string="Dernier achat",
        readonly=True,
    )
    days_since_last_purchase = fields.Integer(
        string="Jours depuis dernier achat",
        readonly=True,
    )
