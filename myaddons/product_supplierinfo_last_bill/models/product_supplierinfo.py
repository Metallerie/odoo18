# `models/product_supplierinfo.py`

```python
from odoo import api, fields, models


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
        """Prépare les valeurs supplierinfo à partir d'une ligne de facture fournisseur validée."""
        product = line.product_id
        move = line.move_id
        partner = move.partner_id

        price = line.price_unit or 0.0
        if line.discount:
            price = price * (1 - (line.discount / 100.0))

        vals = {
            'name': partner.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_id': product.id if product.product_variant_count > 1 else product.id,
            'price': price,
            'currency_id': move.currency_id.id,
            'product_uom': line.product_uom_id.id,
            'min_qty': 1.0,
            'company_id': move.company_id.id,
            'x_last_account_move_id': move.id,
            'x_last_account_move_name': move.name,
        }
        return vals

    @api.model
    def _find_matching_supplierinfo(self, line):
        """Cherche une ligne existante par fournisseur + variante (ou template)."""
        product = line.product_id
        move = line.move_id
        domain = [
            ('name', '=', move.partner_id.id),
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
            ('company_id', 'in', [False, move.company_id.id]),
        ]

        # Si variante, on force la variante
        domain.append(('product_id', '=', product.id))

        return self.search(domain, limit=1, order='sequence, min_qty, id desc')

    @api.model
    def sync_from_move_line(self, line):
        """Crée ou met à jour supplierinfo depuis une ligne de facture fournisseur validée."""
        if not line.product_id:
            return False
        if line.display_type:
            return False
        if line.move_id.move_type != 'in_invoice':
            return False
        if line.move_id.state != 'posted':
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
                    break
            if changed:
                supplierinfo.write(vals)
            return supplierinfo

        return self.create(vals)

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

        return self.env['account.move.line'].search(
            domain,
            order='move_id.invoice_date desc, move_id.id desc, id desc',
            limit=1,
        )

    @api.model
    def rebuild_supplierinfo_for_product(self, product, partner=None, company=None):
        """Recalcule la ligne supplierinfo d'un produit depuis la dernière facture fournisseur validée."""
        latest_line = self._get_latest_posted_vendor_bill_line(product, partner=partner, company=company)
        if latest_line:
            return self.sync_from_move_line(latest_line)

        domain = [('product_tmpl_id', '=', product.product_tmpl_id.id), ('product_id', '=', product.id)]
        if partner:
            domain.append(('name', '=', partner.id))
        if company:
            domain.append(('company_id', 'in', [False, company.id]))
        supplierinfos = self.search(domain)
        if supplierinfos:
            supplierinfos.unlink()
        return False

    @api.model
    def rebuild_all_from_posted_bills(self):
        """Reconstruit toute la table depuis les factures fournisseur validées."""
        self.search([]).unlink()

        lines = self.env['account.move.line'].search([
            ('product_id', '!=', False),
            ('display_type', '=', False),
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', '=', 'in_invoice'),
        ], order='move_id.invoice_date asc, move_id.id asc, id asc')

        for line in lines:
            self.sync_from_move_line(line)

        return True
```

# `models/account_move.py`

```python
from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _supplierinfo_target_lines(self):
        self.ensure_one()
        return self.invoice_line_ids.filtered(
            lambda l: l.product_id and not l.display_type and self.move_type == 'in_invoice'
        )

    def action_post(self):
        res = super().action_post()
        supplierinfo_model = self.env['product.supplierinfo']

        for move in self.filtered(lambda m: m.move_type == 'in_invoice' and m.state == 'posted'):
            for line in move._supplierinfo_target_lines():
                supplierinfo_model.sync_from_move_line(line)

        return res

    def button_draft(self):
        impacted = []
        for move in self.filtered(lambda m: m.move_type == 'in_invoice'):
            for line in move._supplierinfo_target_lines():
                impacted.append((line.product_id.id, move.partner_id.id, move.company_id.id))

        res = super().button_draft()

        supplierinfo_model = self.env['product.supplierinfo']
        products = self.env['product.product']
        partners = self.env['res.partner']
        companies = self.env['res.company']

        for product_id, partner_id, company_id in set(impacted):
            product = products.browse(product_id)
            partner = partners.browse(partner_id)
            company = companies.browse(company_id)
            supplierinfo_model.rebuild_supplierinfo_for_product(
                product,
                partner=partner,
                company=company,
            )

        return res
```

# `models/__init__.py`

```python
from . import product_supplierinfo
from . import account_move
```

# `__manifest__.py`

```python
{
    'name': 'Product Supplierinfo Last Bill',
    'version': '18.0.1.0.0',
    'summary': 'Met à jour supplierinfo depuis la dernière facture fournisseur validée',
    'category': 'Purchase',
    'author': 'La Métallerie',
    'license': 'LGPL-3',
    'depends': ['product', 'purchase', 'account'],
    'data': [],
    'installable': True,
    'application': False,
}
```

# `__init__.py`

```python
from . import models
```
