# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_docai_scan_json(self):
        """
        Lit le champ docai_json et met à jour les infos de la facture
        """
        for move in self:
            if not move.docai_json:
                raise UserError(_("Aucun JSON DocAI trouvé sur cette facture."))

            try:
                data = json.loads(move.docai_json)

                # ⚠️ Exemple avec Document AI Invoice Parser
                # Il faudra adapter selon ton JSON exact
                entities = {ent.get("type_"): ent.get("mentionText") for ent in data.get("entities", [])}

                vals = {}

                # Numéro de facture
                if "invoice_id" in entities:
                    vals["ref"] = entities["invoice_id"]

                # Date de facture
                if "invoice_date" in entities:
                    vals["invoice_date"] = entities["invoice_date"]

                # Fournisseur
                if "supplier_name" in entities:
                    partner = self.env["res.partner"].search([
                        ("name", "ilike", entities["supplier_name"])
                    ], limit=1)
                    if partner:
                        vals["partner_id"] = partner.id

                # Montants
                if "total_amount" in entities:
                    vals["amount_total"] = entities["total_amount"]

                # Appliquer les modifs
                if vals:
                    move.write(vals)
                    _logger.info(f"✅ Facture {move.id} mise à jour depuis JSON : {vals}")
                else:
                    _logger.warning(f"⚠️ Facture {move.id} : aucun champ reconnu dans JSON")

            except Exception as e:
                _logger.error(f"❌ Erreur parsing JSON DocAI facture {move.id} : {e}")
                raise UserError(_("Erreur parsing JSON : %s") % e)
