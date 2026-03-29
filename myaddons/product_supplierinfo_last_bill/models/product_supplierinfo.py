import logging

from odoo import api, fields, models


_logger = logging.getLogger(__name__)


class ProductSupplierinfo(models.Model):
    _inherit = 'product.supplierinfo'

    x_last_account_move_id = fields.Many2one(
        'account.move',
        string='Dernière facture Odoo',
        readonly=True,
        copy=False,
        index=True,
    )
    x_last_account_move_name = fields.Char(
        string='Réf. dernière facture Odoo',
        readonly=True,
        copy=False,
        index=True,
    )

    @api.model
    def _prepare_supplierinfo_vals_from_move_line(self, line):
        """Prépare les valeurs product.supplierinfo depuis une ligne de facture fournisseur."""
        product = line.product_id
        move = line.move_id
        partner = move.partner_id

        price = line.price_unit or 0.0
        if line.discount:
            price = price * (1 - (line.discount / 100.0))

        vals = {
            'name': partner.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_id': product.id,  # toujours la variante
            'price': price,
            'currency_id': move.currency_id.id,
            'product_uom': line.product_uom_id.id,
            'min_qty': 1.0,
            'company_id': move.company_id.id,
            'x_last_account_move_id': move.id,
            'x_last_account_move_name': move.name,
        }

        _logger.info(
            "SUPPLIERINFO prepare vals | move=%s | line=%s | product=%s | vals=%s",
            move.name,
            line.id,
            product.display_name,
            vals,
        )
        return vals

    @api.model
    def _find_matching_supplierinfo(self, line):
        """Cherche la ligne supplierinfo correspondante par fournisseur + template + variante + société."""
        product = line.product_id
        move = line.move_id

        domain = [
            ('name', '=', move.partner_id.id),
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
            ('product_id', '=', product.id),
            ('company_id', 'in', [False, move.company_id.id]),
        ]

        supplierinfo = self.search(domain, limit=1, order='id desc')

        _logger.info(
            "SUPPLIERINFO search | move=%s | product=%s | domain=%s | found=%s",
            move.name,
            product.display_name,
            domain,
            supplierinfo.ids,
        )
        return supplierinfo

    @api.model
    def sync_from_move_line(self, line):
        """
        Crée ou met à jour supplierinfo depuis une ligne de facture fournisseur validée.
        """
        _logger.info(
            "SUPPLIERINFO sync start | line=%s | move=%s | state=%s | type=%s | product=%s | display_type=%s",
            line.id,
            line.move_id.name,
            line.move_id.state,
            line.move_id.move_type,
            line.product_id.display_name if line.product_id else None,
            line.display_type,
        )

        if not line.product_id:
            _logger.info("SUPPLIERINFO skip | line=%s | reason=no_product", line.id)
            return False

        if line.display_type:
            _logger.info("SUPPLIERINFO skip | line=%s | reason=display_type", line.id)
            return False

        if line.move_id.move_type != 'in_invoice':
            _logger.info("SUPPLIERINFO skip | line=%s | reason=not_vendor_bill", line.id)
            return False

        if line.move_id.state != 'posted':
            _logger.info("SUPPLIERINFO skip | line=%s | reason=not_posted", line.id)
            return False

        supplierinfo = self._find_matching_supplierinfo(line)
        vals = self._prepare_supplierinfo_vals_from_move_line(line)

        if supplierinfo:
            changed = False
            for field_name, value in vals.items():
                current = supplierinfo[field_name]
                if hasattr(current, 'id'):
                    current = current.id
                if current != value:
                    changed = True
                    _logger.info(
                        "SUPPLIERINFO diff | supplierinfo=%s | field=%s | current=%s | new=%s",
                        supplierinfo.id,
                        field_name,
                        current,
                        value,
                    )
                    break

            if changed:
                supplierinfo.write(vals)
                _logger.info(
                    "SUPPLIERINFO updated | supplierinfo=%s | move=%s | product=%s",
                    supplierinfo.id,
                    line.move_id.name,
                    line.product_id.display_name,
                )
            else:
                _logger.info(
                    "SUPPLIERINFO unchanged | supplierinfo=%s | move=%s | product=%s",
                    supplierinfo.id,
                    line.move_id.name,
                    line.product_id.display_name,
                )
            return supplierinfo

        new_supplierinfo = self.create(vals)
        _logger.info(
            "SUPPLIERINFO created | supplierinfo=%s | move=%s | product=%s",
            new_supplierinfo.id,
            line.move_id.name,
            line.product_id.display_name,
        )
        return new_supplierinfo

    @api.model
    def _get_latest_posted_vendor_bill_line(self, product, partner=None, company=None):
        domain = [
            ('product_id', '=', product.id),
            ('display_type', '=', False),
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', '=', 'in_invoice'),
        ]
        if partner:
            domain.append(('move_id.partner_id', '=', partner.id))
        if company:
            domain.append(('move_id.company_id', '=', company.id))

        line = self.env['account.move.line'].search(
            domain,
            order='move_id.invoice_date desc, move_id.id desc, id desc',
            limit=1,
        )

        _logger.info(
            "SUPPLIERINFO latest bill line | product=%s | partner=%s | company=%s | line=%s",
            product.display_name,
            partner.display_name if partner else None,
            company.display_name if company else None,
            line.id if line else None,
        )
        return line

    @api.model
    def rebuild_supplierinfo_for_product(self, product, partner=None, company=None):
        """
        Recalcule la ligne supplierinfo d'un produit à partir de la dernière
        facture fournisseur encore validée.
        """
        _logger.info(
            "SUPPLIERINFO rebuild product start | product=%s | partner=%s | company=%s",
            product.display_name,
            partner.display_name if partner else None,
            company.display_name if company else None,
        )

        latest_line = self._get_latest_posted_vendor_bill_line(
            product,
            partner=partner,
            company=company,
        )
        if latest_line:
            _logger.info(
                "SUPPLIERINFO rebuild using latest line | product=%s | line=%s | move=%s",
                product.display_name,
                latest_line.id,
                latest_line.move_id.name,
            )
            return self.sync_from_move_line(latest_line)

        domain = [
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
            ('product_id', '=', product.id),
        ]
        if partner:
            domain.append(('name', '=', partner.id))
        if company:
            domain.append(('company_id', 'in', [False, company.id]))

        supplierinfos = self.search(domain)
        if supplierinfos:
            _logger.info(
                "SUPPLIERINFO rebuild delete obsolete | product=%s | supplierinfos=%s",
                product.display_name,
                supplierinfos.ids,
            )
            supplierinfos.unlink()

        _logger.info(
            "SUPPLIERINFO rebuild done no latest bill | product=%s",
            product.display_name,
        )
        return False

    @api.model
    def rebuild_all_from_posted_bills(self):
        """
        Reconstruit toute la table product.supplierinfo depuis les factures fournisseur validées.
        """
        _logger.info("SUPPLIERINFO rebuild all start")

        existing = self.search([])
        _logger.info("SUPPLIERINFO rebuild all delete existing count=%s", len(existing))
        existing.unlink()

        lines = self.env['account.move.line'].search([
            ('product_id', '!=', False),
            ('display_type', '=', False),
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', '=', 'in_invoice'),
        ], order='move_id.invoice_date asc, move_id.id asc, id asc')

        _logger.info("SUPPLIERINFO rebuild all source lines count=%s", len(lines))

        for line in lines:
            self.sync_from_move_line(line)

        _logger.info("SUPPLIERINFO rebuild all done")
        return True
