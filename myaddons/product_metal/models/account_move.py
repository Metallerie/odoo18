from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    stock_picking_id = fields.Many2one('stock.picking', string="Bon de réception lié")

    def action_create_stock_picking(self):
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']
        Location = self.env.ref('stock.stock_location_suppliers')

        for move in self:
            if move.stock_picking_id:
                continue

        # 🛠 Corrige les produits consu + is_storable → type = 'product'
        corrections = 0
        for line in move.invoice_line_ids:
            tmpl = line.product_id.product_tmpl_id
            if tmpl.type == 'consu' and tmpl.is_storable:
                corrections += 1

        if corrections:
            move.message_post(body=f"🔁 {corrections} produit(s) corrigé(s) automatiquement en 'Stocké'.")

        # 🎯 Création du picking
        picking = StockPicking.create({
            'partner_id': move.partner_id.id,
            'picking_type_id': self.env.ref('stock.picking_type_in').id,
            'location_id': Location.id,
            'location_dest_id': move.company_id.partner_id.property_stock_supplier.id,
            'origin': move.name,
        })

        for line in move.invoice_line_ids:
            product = line.product_id
            if product and product.product_tmpl_id.type == 'consu':
                StockMove.create({
                    'product_id': product.id,
                    'name': f"{move.name} - {product.display_name}",
                    'product_uom_qty': line.quantity,
                    'product_uom': product.uom_po_id.id,
                    'picking_id': picking.id,
                    'location_id': Location.id,
                    'location_dest_id': move.company_id.partner_id.property_stock_supplier.id,
                })

        move.stock_picking_id = picking.id
        move.message_post(body=f"📦 Bon de réception <b>{picking.name}</b> créé.")
        return True

        def action_validate_stock_picking(self):
            for move in self:
                if move.stock_picking_id and move.stock_picking_id.state == 'draft':
                    move.stock_picking_id.action_confirm()
                    move.stock_picking_id.action_assign()
                    move.stock_picking_id.button_validate()
                    move.message_post(body=f"✅ Bon de réception <b>{move.stock_picking_id.name}</b> validé.")
            return True
