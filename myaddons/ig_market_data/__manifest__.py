# ig_market_data/__manifest__.py
{
    "name": "IG Market Data",
    "version": "18.0.1.0.0",
    "summary": "Collect IG market candles and analyze Asia opening impulse",
    "category": "Tools",
    "license": "LGPL-3",
    "author": "Metallerie",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/ig_instrument_views.xml",
        "views/ig_asia_session_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
}
