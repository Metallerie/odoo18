# -*- coding: utf-8 -*-

from odoo import api, fields, models


class QuickQuoteWizard(models.TransientModel):
    _name = "quick.quote.wizard"
    _description = "Assistant devis rapide"

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Devis",
        required=True,
        readonly=True,
    )

    communication_text = fields.Text(
        string="Texte libre de communication"
    )

    generated_text = fields.Text(
        string="Texte à copier",
        compute="_compute_generated_text",
        readonly=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        related="sale_order_id.currency_id",
        store=False,
        readonly=True,
    )

    @api.depends(
        "sale_order_id",
        "sale_order_id.amount_total",
        "sale_order_id.order_line.sequence",
        "sale_order_id.order_line.display_type",
        "sale_order_id.order_line.name",
        "sale_order_id.order_line.product_uom_qty",
        "sale_order_id.order_line.product_uom.name",
        "sale_order_id.order_line.price_unit",
        "sale_order_id.order_line.price_subtotal",
        "sale_order_id.order_line.quick_quote_in_stock",
        "communication_text",
    )
    def _compute_generated_text(self):
        for wizard in self:
            parts = [
                "Bonjour,",
                "",
                "Merci pour votre demande.",
                "",
                "Voici la proposition pour le matériel :",
                "",
            ]

            order = wizard.sale_order_id
            lines = order.order_line.sorted(key=lambda l: (l.sequence, l.id))
            has_out_of_stock = False

            for line in lines:
                if line.display_type == "line_section":
                    if line.name:
                        if parts and parts[-1] != "":
                            parts.append("")
                        parts.append(line.name.strip())
                        parts.append("")
                    continue

                if line.display_type == "line_note":
                    if line.name:
                        parts.append(line.name.strip())
                    continue

                product_label, inline_notes = wizard._split_product_and_notes(line)

                qty = wizard._format_quantity(line.product_uom_qty)
                uom_name = (line.product_uom.name or "").strip()
                unit_price = wizard._format_amount(line.price_unit)
                subtotal = wizard._format_amount(line.price_subtotal)

                if parts and parts[-1] != "":
                    parts.append("")

                parts.append(
                    f"{product_label} : {qty} {uom_name} x {unit_price} = {subtotal}"
                )

                formatted_notes = wizard._format_inline_notes(inline_notes)
                for extra_line in formatted_notes:
                    parts.append(extra_line)

                if line.quick_quote_in_stock:
                    parts.append("Disponible à l’atelier.")
                else:
                    parts.append("Disponible sur commande.")
                    has_out_of_stock = True

            if parts and parts[-1] != "":
                parts.append("")

            parts.append(f"Total : {wizard._format_amount(order.amount_total)}")

            if wizard.communication_text:
                parts.append("")
                parts.append(wizard.communication_text.strip())

            if has_out_of_stock:
                parts.append("")
                parts.append(
                    "Pour les produits sur commande, merci de confirmer avant lundi "
                    "pour l’arrivage de mardi."
                )
                parts.append("Commande possible sur : https://www.metallerie.xyz/shop")

            parts.append("")
            parts.append("Retrait à l’atelier : La Métallerie, Corneilla-del-Vercol")
            parts.append("Tél. 06 25 15 91 20")
            parts.append("")
            parts.append("TVA non applicable, art. 293 B du CGI")
            parts.append("Plus de prix sur : metallerie.xyz/shop")

            wizard.generated_text = "\n".join(parts).strip()

    def _split_product_and_notes(self, line):
        raw_name = (line.name or "").strip()
        raw_lines = [l.strip() for l in raw_name.splitlines() if l.strip()]

        if raw_lines:
            product_label = raw_lines[0]
            inline_notes = raw_lines[1:]
        else:
            product_label = (line.product_id.name or "").strip()
            inline_notes = []

        # Enlève la référence produit : [71651]
        if product_label.startswith("[") and "]" in product_label:
            product_label = product_label.split("]", 1)[1].strip()

        return product_label, inline_notes

    def _format_inline_notes(self, inline_notes):
        formatted = []

        cut_qty = False
        cut_length = False
        total_length = False
        has_relicat = False

        for note in inline_notes:
            clean_note = (note or "").strip()

            if not clean_note:
                continue

            if "Nombre de coupes" in clean_note and "Quantité:" in clean_note:
                cut_qty = clean_note.split("Quantité:")[-1].strip()
                continue

            if "Longueur de coupe" in clean_note and "Dimension:" in clean_note:
                cut_length = clean_note.split("Dimension:")[-1].strip()
                continue

            if "Calcule quantité" in clean_note and "Longueur totale coupée:" in clean_note:
                total_length = clean_note.split("Longueur totale coupée:")[-1].strip()
                continue

            if "Relicat" in clean_note or "Reliquat" in clean_note:
                has_relicat = True
                continue

            formatted.append(clean_note)

        if cut_qty or cut_length or total_length or has_relicat:
            formatted.append("")
            formatted.append("Découpe prévue :")

            if cut_qty and cut_length:
                formatted.append(
                    f"- {cut_qty} morceaux de {self._format_meter_value(cut_length)}"
                )
            elif cut_qty:
                formatted.append(f"- Nombre de morceaux : {cut_qty}")
            elif cut_length:
                formatted.append(
                    f"- Longueur de coupe : {self._format_meter_value(cut_length)}"
                )

            if total_length:
                formatted.append(
                    f"- Longueur totale coupée : {self._format_meter_value(total_length)}"
                )

            if has_relicat and cut_qty and cut_length:
                self._append_cutting_plan(
                    formatted=formatted,
                    cut_qty=cut_qty,
                    cut_length=cut_length,
                )
            elif has_relicat:
                formatted.append("- Chute / reliquat : à calculer")

        return formatted

    def _append_cutting_plan(self, formatted, cut_qty, cut_length):
        """
        Ajoute le calcul de chute/reliquat dans les lignes du devis.
        Pour l’instant conditionnement fixe à 6,15 m.
        """
        conditionnement = 6.15

        try:
            qty_int = int(float(str(cut_qty).replace(",", ".")))
            length_float = float(str(cut_length).replace(",", "."))

            plan = self._compute_cutting_plan(
                quantity=qty_int,
                piece_length=length_float,
                conditionnement=conditionnement,
            )

            if not plan or not plan.get("total_bars"):
                formatted.append("- Chute / reliquat : à calculer")
                return

            formatted.append(
                f"- Conditionnement utilisé : "
                f"{plan['total_bars']} barre(s) de {self._format_meter_value(conditionnement)}"
            )

            scraps = self._group_lengths(plan.get("scraps", []))
            stockable = self._group_lengths(plan.get("stockable", []))

            if scraps:
                formatted.append("- Chutes facturées :")
                for scrap in scraps:
                    formatted.append(f"  • {scrap}")

            if stockable:
                formatted.append("- Reliquats conservés atelier :")
                for stock in stockable:
                    formatted.append(f"  • {stock}")

        except Exception:
            formatted.append("- Chute / reliquat : erreur de calcul")

    def _compute_cutting_plan(self, quantity, piece_length, conditionnement):
        """
        Calcul simple de débit par barre.

        Règle :
        - on calcule combien de morceaux rentrent dans une barre
        - on débite barre par barre
        - les mètres entiers du reste sont conservés atelier
        - la partie inférieure à 1 m est considérée comme chute facturée
        """
        result = {
            "bars": [],
            "total_bars": 0,
            "scraps": [],
            "stockable": [],
        }

        if quantity <= 0 or piece_length <= 0 or conditionnement <= 0:
            return result

        pieces_per_bar = int(conditionnement // piece_length)

        if pieces_per_bar <= 0:
            return result

        remaining_pieces = int(quantity)

        while remaining_pieces > 0:
            current_pieces = min(pieces_per_bar, remaining_pieces)

            used_length = round(current_pieces * piece_length, 2)
            remainder = round(conditionnement - used_length, 2)

            stock_part = int(remainder)
            scrap_part = round(remainder - stock_part, 2)

            bar_data = {
                "pieces": current_pieces,
                "used_length": used_length,
                "remainder": remainder,
                "stockable": stock_part,
                "scrap": scrap_part,
            }

            result["bars"].append(bar_data)

            if stock_part > 0:
                result["stockable"].append(float(stock_part))

            if scrap_part > 0:
                result["scraps"].append(scrap_part)

            remaining_pieces -= current_pieces

        result["total_bars"] = len(result["bars"])

        return result

    def _group_lengths(self, values):
        grouped = {}

        for value in values:
            value = round(float(value), 2)
            grouped[value] = grouped.get(value, 0) + 1

        result = []

        for length, qty in sorted(grouped.items()):
            formatted_length = self._format_meter_value(length)
            result.append(f"{qty} x {formatted_length}")

        return result

    def _format_meter_value(self, value):
        value = str(value or "").strip().replace(",", ".")

        try:
            number = float(value)
            formatted = f"{number:g}".replace(".", ",")
            return f"{formatted} m"
        except Exception:
            return f"{value} m"

    def _format_amount(self, amount):
        self.ensure_one()
        currency_symbol = self.currency_id.symbol or "€"
        value = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", " ")

        if self.currency_id.position == "before":
            return f"{currency_symbol}{value}"

        return f"{value} {currency_symbol}"

    def _format_quantity(self, qty):
        value = f"{qty:g}"
        return value.replace(".", ",")
