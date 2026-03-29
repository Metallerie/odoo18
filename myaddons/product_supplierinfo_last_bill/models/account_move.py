import logging

from odoo import models


_logger = logging.getLogger(__name__)
_logger.warning("SUPPLIERINFO account_move.py chargé")

class AccountMove(models.Model):
    _inherit = 'account.move'

    def _supplierinfo_target_lines(self):
        self.ensure_one()

        lines = self.invoice_line_ids.filtered(
            lambda l: l.product_id
            and not l.display_type
            and self.move_type == 'in_invoice'
        )

        _logger.info(
            "SUPPLIERINFO target lines | move=%s | move_id=%s | lines=%s",
            self.name,
            self.id,
            lines.ids,
        )
        return lines

    def action_post(self):
        _logger.info("SUPPLIERINFO action_post start | moves=%s", self.ids)

        res = super().action_post()
        supplierinfo_model = self.env['product.supplierinfo']

        for move in self.filtered(lambda m: m.move_type == 'in_invoice' and m.state == 'posted'):
            _logger.info(
                "SUPPLIERINFO action_post processing | move=%s | move_id=%s",
                move.name,
                move.id,
            )
            for line in move._supplierinfo_target_lines():
                _logger.info(
                    "SUPPLIERINFO action_post line | move=%s | line=%s | product=%s",
                    move.name,
                    line.id,
                    line.product_id.display_name,
                )
                supplierinfo_model.sync_from_move_line(line)

        _logger.info("SUPPLIERINFO action_post end | moves=%s", self.ids)
        return res

    def button_draft(self):
        _logger.info("SUPPLIERINFO button_draft start | moves=%s", self.ids)

        impacted = []
        for move in self.filtered(lambda m: m.move_type == 'in_invoice'):
            _logger.info(
                "SUPPLIERINFO button_draft collect | move=%s | move_id=%s | state=%s",
                move.name,
                move.id,
                move.state,
            )
            for line in move._supplierinfo_target_lines():
                impacted.append((line.product_id.id, move.partner_id.id, move.company_id.id))
                _logger.info(
                    "SUPPLIERINFO button_draft impacted | move=%s | line=%s | product=%s",
                    move.name,
                    line.id,
                    line.product_id.display_name,
                )

        res = super().button_draft()

        supplierinfo_model = self.env['product.supplierinfo']
        products = self.env['product.product']
        partners = self.env['res.partner']
        companies = self.env['res.company']

        for product_id, partner_id, company_id in set(impacted):
            product = products.browse(product_id)
            partner = partners.browse(partner_id)
            company = companies.browse(company_id)

            _logger.info(
                "SUPPLIERINFO button_draft rebuild | product=%s | partner=%s | company=%s",
                product.display_name,
                partner.display_name,
                company.display_name,
            )

            supplierinfo_model.rebuild_supplierinfo_for_product(
                product,
                partner=partner,
                company=company,
            )

        _logger.info("SUPPLIERINFO button_draft end | moves=%s", self.ids)
        return res
