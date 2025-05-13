from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    purchase_order_id = fields.Many2one('purchase.order', string="Bon de commande lié")

    def action_create_purchase_order_from_invoice(self):
        PurchaseOrder = self.env['purchase.order']
        PurchaseOrderLine = self.env['purchase.order.line']

        for move in self:
            if move.purchase_order_id:
                raise UserError("📌 Cette facture est déjà liée à un bon de commande.")

            if move.move_type != 'in_invoice':
                raise UserError("⚠️ Cette action n'est possible que pour les factures fournisseurs.")

            if move.state != 'posted':
                raise UserError("❌ La facture doit être validée avant de générer un bon de commande.")

            if not move.invoice_line_ids:
                raise UserError("⚠️ Aucune ligne de produit détectée sur cette facture.")

            # Création de la commande fournisseur
            po = PurchaseOrder.create({
                'partner_id': move.partner_id.id,
                'origin': move.name,
                'date_order': fields.Date.today(),
            })

            for line in move.invoice_line_ids.filtered(lambda l: l.product_id and l.quantity > 0):
                PurchaseOrderLine.create({
                    'order_id': po.id,
                    'product_id': line.product_id.id,
                    'name': line.name or line.product_id.display_name,
                    'product_qty': line.quantity,
                    'product_uom': line.product_uom_id.id or line.product_id.uom_po_id.id,
                    'price_unit': line.price_unit or 0.0,
                    'date_planned': fields.Date.today(),
                })

            move.purchase_order_id = po.id
            move.message_post(body=f"🛒 Bon de commande <b>{po.name}</b> créé automatiquement.")
            po.message_post(body=f"📄 Créé à partir de la facture <b>{move.name}</b>.")

        return True
def action_validate_purchase_and_create_receipt(self):
    StockPicking = self.env['stock.picking']
    StockMove = self.env['stock.move']
    Location = self.env.ref('stock.stock_location_suppliers')

    for move in self:
        if not move.purchase_order_id:
            continue

        # ✅ Valide la commande fournisseur
        if move.purchase_order_id.state not in ['purchase', 'done']:
            move.purchase_order_id.button_confirm()

        picking_type_in = self.env.ref('stock.picking_type_in')
        picking = StockPicking.create({
            'partner_id': move.partner_id.id,
            'picking_type_id': picking_type_in.id,
            'location_id': Location.id,
            'location_dest_id': move.company_id.partner_id.property_stock_supplier.id,
            'origin': move.name,
        })

        for po_line in move.purchase_order_id.order_line:
            product = po_line.product_id
            qty_po = po_line.product_qty
            qty_stock = qty_po

            # 📦 Conversion kg ➜ ml
            if product.uom_po_id.name.lower() in ['kg', 'kilogramme'] and product.product_kg_ml > 0:
                qty_stock = qty_po / product.product_kg_ml

            # 👇 Création du stock.move
            StockMove.create({
                'product_id': product.id,
                'name': f"{move.name} - {product.display_name}",
                'product_uom_qty': qty_stock,
                'product_uom': product.uom_id.id,
                'picking_id': picking.id,
                'location_id': Location.id,
                'location_dest_id': move.company_id.partner_id.property_stock_supplier.id,
            })

        move.message_post(body=f"📦 Bon de réception <b>{picking.name}</b> créé à partir de la commande.")
