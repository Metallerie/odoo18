from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class EcotaxSetupWizard(models.TransientModel):
    _name = 'mindee_ai.ecotax_setup_wizard'
    _description = "Assistant de configuration de l'écotaxe"

    apply_to_products = fields.Boolean(string="Ajouter la taxe aux produits (cornière, plat, carré)", default=True)

    def action_setup_ecotax(self):
        # 1. Créer la taxe si elle n'existe pas
        Tax = self.env['account.tax']
        ecotax = Tax.search([('name', '=', 'Éco-part')], limit=1)
        if not ecotax:
            ecotax = Tax.create({
                'name': 'Éco-part',
                'amount': 0.002,
                'amount_type': 'fixed',
                'type_tax_use': 'purchase',
                'price_include': False,
                'active': True,
                'description': 'Écotaxe 0.002€/kg',
            })
            _logger.info("Taxe Éco-part créée.")

        # 2. Créer le produit éco-participation
        Product = self.env['product.product']
        ecotax_product = Product.search([('default_code', '=', 'ECO-TAXE')], limit=1)
        if not ecotax_product:
            ecotax_product = self.env['product.product'].create({
                'name': 'Éco-participation',
                'default_code': 'ECO-TAXE',
                'type': 'service',
                'uom_id': self.env.ref('uom.product_uom_kgm').id,
                'list_price': 0.002,
                'standard_price': 0.002,
                'purchase_ok': False,
                'sale_ok': False,
            })
            _logger.info("Produit Éco-participation créé.")

        # 3. Ajouter la taxe aux produits concernés
        if self.apply_to_products:
            ProductTmpl = self.env['product.template']
            target_products = ProductTmpl.search([
                '|', '|',
                ('name', 'ilike', 'cornière'),
                ('name', 'ilike', 'plat'),
                ('name', 'ilike', 'carré'),
            ])
            for tmpl in target_products:
                tmpl.write({'supplier_taxes_id': [(6, 0, [ecotax.id])]})
            _logger.info(f"{len(target_products)} produits mis à jour avec la taxe Éco-part.")

        return {'type': 'ir.actions.act_window_close'}
