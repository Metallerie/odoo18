
from markupsafe import Markup, escape

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_mail_line_details_html(self):
        self.ensure_one()

        rows = ""
        for line in self.invoice_line_ids:
            if line.display_type:
                continue

            rows += f"""
                <tr>
                    <td style="padding:6px;border:1px solid #ddd;">{escape(line.name or "")}</td>
                    <td style="padding:6px;border:1px solid #ddd;text-align:right;">{line.quantity:g}</td>
                    <td style="padding:6px;border:1px solid #ddd;">{escape(line.product_uom_id.name or "")}</td>
                    <td style="padding:6px;border:1px solid #ddd;text-align:right;">{line.price_unit:.2f}</td>
                    <td style="padding:6px;border:1px solid #ddd;text-align:right;">{line.price_subtotal:.2f}</td>
                </tr>
            """

        if not rows:
            return Markup("")

        html = f"""
            <div style="margin-top:16px;margin-bottom:16px;">
                <p><strong>Détail du document :</strong></p>
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
        """
        return Markup(html)
