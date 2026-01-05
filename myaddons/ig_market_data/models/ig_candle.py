# ig_market_data/models/ig_candle.py
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class IgCandle(models.Model):
    _name = "ig.candle"
    _description = "IG Candle"
    _order = "timestamp desc"
    _sql_constraints = [
        ("uniq_candle", "unique(instrument_id,timeframe,timestamp)",
         "This candle already exists for this instrument/timeframe/timestamp.")
    ]

    instrument_id = fields.Many2one("ig.instrument", required=True, index=True, ondelete="cascade")
    timeframe = fields.Selection([
        ("M1", "1 min"),
        ("M5", "5 min"),
        ("M15", "15 min"),
        ("H1", "1 hour"),
        ("D1", "1 day"),
    ], required=True, default="M5", index=True)

    timestamp = fields.Datetime(required=True, index=True)  # UTC conseillé
    open = fields.Float(required=True)
    high = fields.Float(required=True)
    low = fields.Float(required=True)
    close = fields.Float(required=True)
    volume = fields.Float()

    @api.constrains("high", "low", "open", "close")
    def _check_prices(self):
        for r in self:
            if r.low > r.high:
                raise ValidationError("low cannot be > high")
