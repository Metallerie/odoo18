# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    purchase_order_id = fields.Many2one('purchase.order', string="Bon de commande lié")
    stock_picking_id = fields.Many2one('stock.picking', string="Bon de réception")

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

            po = PurchaseOrder.create({
                'partner_id': move.partner_id.id,
                'origin': move.name,
                'partner_ref': move.ref,
                'date_order': fields.Date.today(),
            })

            for line in move.invoice_line_ids.filtered(lambda l: l.product_id and l.quantity > 0):
                PurchaseOrderLine.create({
                    'order_id': po.id,
                    'product_id': line.product_id.id,
                    'name': line.name or line.product_id.display_name,
                    'product_qty': line.quantity,
                    'qty_received': line.quantity,
                    'product_uom': line.product_uom_id.id or line.product_id.uom_po_id.id,
                    'price_unit': line.price_unit or 0.0,
                    'date_planned': fields.Date.today(),
                })

            move.purchase_order_id = po.id
            move.message_post(body=f"🛒 Bon de commande <b>{po.name}</b> créé automatiquement.")
            po.message_post(body=f"📄 Créé à partir de la facture <b>{move.name}</b>.")

        return True

    def action_validate_purchase_order(self):
        for move in self:
            po = move.purchase_order_id
            if not po:
                raise UserError("❌ Aucun bon de commande lié.")
            if po.state not in ('draft', 'sent'):
                raise UserError("❌ Le bon de commande est déjà validé.")
            
            po.with_context({}).button_confirm()
            move.message_post(body=f"✅ Bon de commande <b>{po.name}</b> validé.")
        return True

    def action_create_receipt_from_po(self):
        for move in self:
            po = move.purchase_order_id
            if not po or po.state != 'purchase':
                raise UserError("⚠️ Le bon de commande n'est pas validé ou introuvable.")
            if move.stock_picking_id:
                raise UserError("🚫 Une réception est déjà liée à cette facture.")

            # 🔍 Récupération du picking existant
            picking = po.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')).sorted(key='id', reverse=True)[:1]
            if not picking:
                raise UserError("Aucun bon de réception trouvé pour ce bon de commande.")

            # ✅ Confirmer et remplir les quantités
            picking.action_confirm()
            for stock_move in picking.move_ids_without_package:
                product = stock_move.product_id
                qty = stock_move.product_uom_qty

                po_line = po.order_line.filtered(lambda l: l.product_id == product)
                if product.product_kg_ml > 0 and stock_move.product_uom.name.lower() == 'kg':
                    qty = qty / product.product_kg_ml


                self.env['stock.move.line'].create({
                    'picking_id': picking.id,
                    'move_id': stock_move.id,
                    'product_id': product.id,
                    'product_uom_id': stock_move.product_uom.id,
                    'quantity': qty,  # ✅ Champ correct
                    'quantity_product_uom': qty,  # ✅ Champ correct
                    'description_picking': f"Achat en {stock_move.product_uom.name} → Conversion : {round(qty, 3)} ML",
                    'location_id': stock_move.location_id.id,
                    'location_dest_id': stock_move.location_dest_id.id,
                })

            picking.button_validate()
            move.stock_picking_id = picking.id
            move.message_post(body=f"📦 Bon de réception <b>{picking.name}</b> validé à partir du bon de commande <b>{po.name}</b>.")

        return True
