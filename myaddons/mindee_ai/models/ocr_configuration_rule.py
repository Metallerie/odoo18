from odoo import models, fields, api
from odoo.exceptions import ValidationError

# Définition des variables disponibles pour les règles OCR
VARIABLE_SELECTION = [
    ('total_amount', 'Total Amount'),
    ('line_count', 'Line Count'),
    ('total_net', 'Total Net'),
    ('total_tax', 'Total Tax'),
    ('partner_name', 'Partner Name'),
    ('invoice_date', 'Invoice Date'),
    ('invoice_number', 'Invoice Number'),
    # Ajouter d'autres variables ici si nécessaire
]

class OcrRule(models.Model):
    _name = "ocr.configuration.rule"
    _description = "OCR Configuration Rules"

    # Identification de la règle
    name = fields.Char(string="Rule Name", required=True)
    partner_id = fields.Many2one(
        'res.partner', 
        string="Partner", 
        ondelete='cascade', 
        help="Targeted partner for this rule."
    )
    global_rule = fields.Boolean(
        string="Global Rule", 
        default=False, 
        help="Applies to all partners if no specific partner is selected."
    )
    sequence = fields.Integer(
        string="Sequence", 
        required=True, 
        default=10, 
        help="Order of rule application."
    )
    active = fields.Boolean(string="Active", default=True)

    # Définition des variables, types et conditions
    variable = fields.Selection(
        selection=VARIABLE_SELECTION, 
        string="Variable", 
        required=True
    )
    condition_type = fields.Selection([
        ('number', 'Number'),
        ('text', 'Text'),
        ('date', 'Date')
    ], string="Condition Type", required=True, default='number')
    operator = fields.Selection([
        ('==', '='), 
        ('<=', '<='), 
        ('<', '<'), 
        ('>=', '>='), 
        ('>', '>'),
        ('contains', 'Contains'),
        ('startswith', 'Starts With'),
        ('endswith', 'Ends With')
    ], string="Operator", required=True, default='==')

    # Valeurs pour les comparaisons
    value = fields.Float(
        string="Numeric Value", 
        help="Maximum or reference value for numerical comparisons."
    )
    value_text = fields.Char(
        string="Text Value", 
        help="Text value for string-based comparisons."
    )
    value_date = fields.Date(
        string="Date Value", 
        help="Reference date for date-based conditions."
    )

    # Valeur lisible pour l'affichage
    value_display = fields.Char(
        string="Value (Display)", 
        compute="_compute_value_display", 
        store=False
    )

    @api.depends('value', 'value_text', 'value_date', 'condition_type')
    def _compute_value_display(self):
        for rule in self:
            if rule.condition_type == 'number':
                rule.value_display = str(rule.value) if rule.value is not None else ''
            elif rule.condition_type == 'text':
                rule.value_display = rule.value_text or ''
            elif rule.condition_type == 'date':
                rule.value_display = rule.value_date.strftime('%Y-%m-%d') if rule.value_date else ''
            else:
                rule.value_display = ''

    # Contraintes et validations
    @api.constrains('variable', 'value', 'operator', 'condition_type')
    def _check_rule_consistency(self):
        for rule in self:
            if rule.condition_type == 'number' and rule.value is None:
                raise ValidationError("A numeric value is required for numerical comparisons.")
            if rule.condition_type == 'text' and not rule.value_text:
                raise ValidationError("A text value is required for text-based comparisons.")
            if rule.condition_type == 'date' and not rule.value_date:
                raise ValidationError("A date value is required for date-based comparisons.")
