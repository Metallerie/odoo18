# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.exceptions import UserError

class IgConfigMixin(models.AbstractModel):
    _name = "ig.config.mixin"
    _description = "IG Config Mixin"

    @api.model
    def ig_get_param(self, key: str, default=None, required: bool = False):
        val = self.env["ir.config_parameter"].sudo().get_param(key, default)
        if required and (val is None or str(val).strip() == ""):
            raise UserError(f"Paramètre système manquant : {key}")
        return val

    @api.model
    def ig_get_config(self) -> dict:
        """Centralise la config IG (lecture seule)."""
        return {
            "base_url": self.ig_get_param("ig.base_url", required=True),
            "api_key": self.ig_get_param("ig.api_key", required=True),
            "username": self.ig_get_param("ig.username", required=True),
            "password": self.ig_get_param("ig.password", required=True),
            "account_id": self.ig_get_param("ig.account_id", default=""),
            "gold_epic": self.ig_get_param("ig.epic.gold", default=""),
        }
