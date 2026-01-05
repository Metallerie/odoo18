# -*- coding: utf-8 -*-
import requests
from odoo import models
from odoo.exceptions import UserError

class IgClient(models.AbstractModel):
    _name = "ig.client"
    _description = "IG API Client (read-only)"

    def _get_config(self):
        cfg = self.env["ig.config.mixin"].ig_get_config()
        return cfg

    def ig_login(self):
        cfg = self._get_config()
        url = f"{cfg['base_url']}/session"

        headers = {
            "X-IG-API-KEY": cfg["api_key"],
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Version": "2",
        }

        payload = {
            "identifier": cfg["username"],
            "password": cfg["password"],
        }

        r = requests.post(url, json=payload, headers=headers, timeout=10)
        if r.status_code not in (200, 201):
            raise UserError(f"IG login failed: {r.status_code} {r.text}")

        cst = r.headers.get("CST")
        xst = r.headers.get("X-SECURITY-TOKEN")

        if not cst or not xst:
            raise UserError("IG login ok but missing tokens")

        return {
            "CST": cst,
            "X-SECURITY-TOKEN": xst,
            "headers": {
                "X-IG-API-KEY": cfg["api_key"],
                "CST": cst,
                "X-SECURITY-TOKEN": xst,
                "Accept": "application/json",
            }
        }

    def ig_get_market(self, epic):
        sess = self.ig_login()
        cfg = self._get_config()
        url = f"{cfg['base_url']}/markets/{epic}"

        r = requests.get(url, headers=sess["headers"], timeout=10)
        if r.status_code != 200:
            raise UserError(f"Market fetch failed: {r.status_code} {r.text}")

        return r.json()
