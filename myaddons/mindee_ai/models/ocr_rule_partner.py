from odoo import models, fields

class OcrRulePartner(models.Model):
    _name = "ocr.configuration.rule.partner"
    _description = "OCR Rules for Partners"
    _order = "sequence, id"

    name = fields.Char(string="Nom de la règle", required=True)
    sequence = fields.Integer(string="Ordre", default=10)
    active = fields.Boolean(string="Active", default=True)

    partner_id = fields.Many2one(
        "res.partner",
        string="Partenaire",
        required=True,
        domain="[('supplier_rank', '>', 0)]",  # ✅ seulement les fournisseurs
        help="Sélectionne un fournisseur existant à associer quand la règle correspond."
    )

    keyword = fields.Char(
        string="Mot-clé",
        required=True,
        help="Texte à rechercher dans la facture OCR (ex: 'leboncoin', 'CCL')."
    )

    search_in = fields.Selection([
        ('raw_text', 'Texte brut'),
        ('invoice_number', 'Numéro de facture'),
        ('partner_name', 'Nom OCR du partenaire'),
    ], string="Champ analysé", default='raw_text', required=True)
