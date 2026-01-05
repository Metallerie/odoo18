# ig_market_data/models/ig_asia_session.py
from datetime import datetime, timedelta, time
from odoo import api, fields, models

class IgAsiaSession(models.Model):
    _name = "ig.asia.session"
    _description = "Asia Opening Analysis"
    _order = "date desc"

    date = fields.Date(required=True, index=True)
    instrument_id = fields.Many2one("ig.instrument", required=True, index=True, ondelete="cascade")

    open_ts = fields.Datetime(index=True)
    close_ts = fields.Datetime(index=True)

    range_pts = fields.Float(help="High-Low during first hour")
    max_up_pts = fields.Float(help="Max up move from open during first hour")
    max_down_pts = fields.Float(help="Max down move from open during first hour")

    signal = fields.Selection([
        ("none", "None"),
        ("long", "Long"),
        ("short", "Short"),
    ], default="none", index=True)

    note = fields.Text()

    _sql_constraints = [
        ("uniq_asia", "unique(date,instrument_id)", "Analysis already exists for this day/instrument.")
    ]

    def action_compute_for_date(self, target_date=None, timeframe="M1"):
        """Compute first-hour Asia stats from candles already stored (no IG calls here)."""
        target_date = target_date or fields.Date.context_today(self)
        instruments = self.env["ig.instrument"].search([("active", "=", True)])

        for inst in instruments:
            # Open time UTC (simplifié) : date à 23:00 UTC la veille, selon inst settings
            # Tu ajusteras selon ta définition "ouverture Asie".
            open_dt = datetime.combine(target_date, time(inst.asia_open_hour_utc, inst.asia_open_minute_utc))
            open_dt = open_dt.replace(tzinfo=None)  # Odoo stocke en naïf UTC en DB
            close_dt = open_dt + timedelta(hours=1)

            candles = self.env["ig.candle"].search([
                ("instrument_id", "=", inst.id),
                ("timeframe", "=", timeframe),
                ("timestamp", ">=", open_dt),
                ("timestamp", "<", close_dt),
            ], order="timestamp asc")

            if not candles:
                continue

            first_open = candles[0].open
            high_ = max(c.high for c in candles)
            low_ = min(c.low for c in candles)

            max_up = high_ - first_open
            max_down = first_open - low_

            rec = self.search([("date", "=", target_date), ("instrument_id", "=", inst.id)], limit=1)
            vals = {
                "open_ts": open_dt,
                "close_ts": close_dt,
                "range_pts": high_ - low_,
                "max_up_pts": max_up,
                "max_down_pts": max_down,
            }
            if rec:
                rec.write(vals)
            else:
                self.create({"date": target_date, "instrument_id": inst.id, **vals})
