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
