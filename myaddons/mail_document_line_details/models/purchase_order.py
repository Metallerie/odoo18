from markupsafe import Markup, escape
from odoo import models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _get_mail_line_details_html(self):
        self.ensure_one()

        rows = ""
        for line in self.order_line:
            if line.display_type:
                continue

            rows += f"""
                <tr>
                    <td style="padding:6px;border:1px solid #ddd;">{escape(line.name or "")}</td>
                    <td style="padding:6px;border:1px solid #ddd;text-align:right;">{line.product_qty:g}</td>
                    <td style="padding:6px;border:1px solid #ddd;">{escape(line.product_uom.name or "")}</td>
                    <td style="padding:6px;border:1px solid #ddd;text-align:right;">{line.price_unit:.2f}</td>
                    <td style="padding:6px;border:1px solid #ddd;text-align:right;">{line.price_subtotal:.2f}</td>
                </tr>
            """

        if not rows:
            return Markup("")

        return Markup(f"""
            <div style="margin-top:16px;margin-bottom:16px;">
                <p><strong>Détail de la commande :</strong></p>
                <table style="border-collapse:collapse;width:100%;font-size:13px;">
                    <thead>
                        <tr style="background-color:#f5f5f5;">
                            <th style="padding:6px;border:1px solid #ddd;text-align:left;">Désignation</th>
                            <th style="padding:6px;border:1px solid #ddd;text-align:right;">Qté</th>
                            <th style="padding:6px;border:1px solid #ddd;text-align:left;">Unité</th>
                            <th style="padding:6px;border:1px solid #ddd;text-align:right;">PU HT</th>
                            <th style="padding:6px;border:1px solid #ddd;text-align:right;">Total HT</th>
                        </tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        """)
