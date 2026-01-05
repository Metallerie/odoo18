# ig_market_data/models/ig_instrument.py
from odoo import api, fields, models

class IgInstrument(models.Model):
    _name = "ig.instrument"
    _description = "IG Instrument"
    _rec_name = "name"
    _order = "name"

    name = fields.Char(required=True)
    epic = fields.Char(help="IG epic (preferred identifier)")
    market_id = fields.Char(help="Alternative IG marketId if needed")
    active = fields.Boolean(default=True)

    # pour la suite
    pip_size = fields.Float(default=0.1)
    currency = fields.Char(default="EUR")

    # sessions (on simplifie : juste des heures)
    asia_open_hour_utc = fields.Integer(default=23)  # exemple, à ajuster
    asia_open_minute_utc = fields.Integer(default=0)

    note = fields.Text()
