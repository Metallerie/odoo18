from odoo import models, fields

class SyncFieldStatus(models.Model):
    _name = 'metallerie.sync.field.status'
    _description = 'Statut de synchronisation des champs'

    field_name = fields.Char(string="Nom du champ")
    field_type = fields.Char(string="Type du champ")
    field_relation = fields.Char(string="Relation")
    field_status = fields.Selection([
        ('synced', 'Synchronisé'),
        ('ignored', 'Ignoré')
    ], string="Statut")
    ignore_reason = fields.Text(string="Raison ignorée")

    # Relation avec le modèle spécifique de synchronisation
    sync_partner_id = fields.Many2one('metallerie.sync.partner', string="Synchronisation Partenaire")
