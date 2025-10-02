# myaddons/mindee_ai/models/account_move.py

import re
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    def _to_float(self, value):
        """Convertit un texte en float (gère virgule, espaces, €)."""
        if not value:
            return None
        try:
            clean = str(value).replace("€", "").replace(",", ".").replace(" ", "")
            return float(clean)
        except Exception:
            return None

    def _header_map(self, header):
        """Déduit la position des colonnes d'après l'entête OCR."""
        hmap = {"ref": None, "desi": None, "qte": None,
                "prix_u": None, "montant": None, "prix_ht": None}
        for i, h in enumerate(header):
            h_low = h.lower()
            if "réf" in h_low or "reference" in h_low:
                hmap["ref"] = i
            elif "désignation" in h_low or "description" in h_low:
                hmap["desi"] = i
            elif "qté" in h_low or "quantité" in h_low:
                hmap["qte"] = i
            elif "prix unitaire" in h_low:
                hmap["prix_u"] = i
            elif "montant" in h_low or "total" in h_low:
                hmap["montant"] = i
            elif "prix ht" in h_low:
                hmap["prix_ht"] = i
        return hmap

    def _find_tax(self, row_text):
        """Détecte la TVA dans une ligne et retourne un Many2many tax_ids."""
        tax_map = {
            "20": 20.0,
            "10": 10.0,
            "5.5": 5.5,
            "5,5": 5.5,
            "0": 0.0,
        }
        match = re.search(r"(\d+[.,]?\d*)\s*%", row_text)
        if match:
            taux = match.group(1).replace(",", ".")
            taux_val = tax_map.get(taux, float(taux))
            tax = self.env["account.tax"].search([("amount", "=", taux_val)], limit=1)
            if tax:
                return [(6, 0, [tax.id])]
        # Si aucune TVA trouvée → taxe par défaut 20%
        tax = self.env["account.tax"].search([("amount", "=", 20.0)], limit=1)
        if tax:
            return [(6, 0, [tax.id])]
        return False

    def _create_invoice_lines_from_ocr(self, ocr_data):
        Product = self.env["product.product"]

        SKIP_ROW_PAT = re.compile(
            r"(frais\s+fixes|base\s+ht|total|net\s+a\s+payer|tva\b|ventilation)",
            re.IGNORECASE
        )

        for move in self:
            if not ocr_data.get("pages"):
                continue

            for page in ocr_data.get("pages", []):
                header = page.get("header", []) or []
                products = page.get("products", []) or []
                hmap = self._header_map(header)

                line_vals = []
                prev_line_idx = None

                for row in products:
                    if not row or all(not (c or "").strip() for c in row):
                        continue

                    row_text = " ".join([c for c in row if c]).strip()

                    if SKIP_ROW_PAT.search(row_text):
                        continue

                    # TVA détectée
                    taxes = self._find_tax(row_text)

                    # Cas spécial Éco-participation
                    if re.search(r"é?eco[- ]?part", row_text, re.IGNORECASE):
                        eco = Product.search([("default_code", "=", "ECO-PART")], limit=1)
                        if not eco:
                            eco = Product.search([("name", "ilike", "éco-participation")], limit=1)
                        if not eco:
                            _logger.warning("[OCR] Produit 'ECO-PART' introuvable → skip : %s", row_text)
                            continue

                        amount = None
                        for c in reversed(row):
                            amount = self._to_float(c)
                            if amount is not None:
                                break

                        line_vals.append({
                            "product_id": eco.id,
                            "name": row_text,
                            "quantity": 1.0,
                            "price_unit": amount or 0.0,
                            "tax_ids": taxes or False,
                        })
                        prev_line_idx = len(line_vals) - 1
                        continue

                    # ---- Mapping colonnes ----
                    ref = None
                    desi = None
                    qty = None
                    price_u = None
                    montant = None

                    if hmap["ref"] is not None and hmap["ref"] < len(row):
                        ref = (row[hmap["ref"]] or "").strip()

                    if hmap["desi"] is not None and hmap["desi"] < len(row):
                        desi = (row[hmap["desi"]] or "").strip()
                    else:
                        desi = row_text

                    if hmap["qte"] is not None and hmap["qte"] < len(row):
                        qty = self._to_float(row[hmap["qte"]])

                    if hmap["prix_u"] is not None and hmap["prix_u"] < len(row):
                        price_u = self._to_float(row[hmap["prix_u"]])

                    if hmap["montant"] is not None and hmap["montant"] < len(row):
                        montant = self._to_float(row[hmap["montant"]])

                    if price_u is None and hmap["prix_ht"] is not None and hmap["prix_ht"] < len(row):
                        price_u = self._to_float(row[hmap["prix_ht"]])

                    if qty is None:
                        qty = 1.0
                    if (price_u is None or price_u == 0.0) and montant is not None and qty:
                        price_u = montant / qty

                    has_number = re.search(r"\d", row_text) is not None
                    if not has_number and prev_line_idx is not None:
                        line_vals[prev_line_idx]["name"] = (line_vals[prev_line_idx]["name"] + " " + desi).strip()
                        continue

                    # Recherche produit
                    product = False
                    if ref:
                        product = Product.search([("default_code", "=", ref)], limit=1)
                    if not product and desi:
                        product = Product.search([("name", "ilike", desi)], limit=1)
                    if not product:
                        product = Product.create({
                            "name": desi or "Produit OCR",
                            "default_code": ref or False,
                            "type": "consu",
                        })

                    line_vals.append({
                        "product_id": product.id,
                        "name": desi or product.display_name,
                        "quantity": qty or 1.0,
                        "price_unit": price_u or 0.0,
                        "tax_ids": taxes or False,
                    })
                    prev_line_idx = len(line_vals) - 1

                if line_vals:
                    move.write({"invoice_line_ids": [(0, 0, vals) for vals in line_vals]})
                    _logger.info("[OCR] %s lignes ajoutées sur %s", len(line_vals), move.name)
