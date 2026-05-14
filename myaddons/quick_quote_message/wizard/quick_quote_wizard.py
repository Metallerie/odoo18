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
        """
        Retourne :
        - le libellé produit propre
        - les lignes complémentaires éventuelles venant du champ name
        """
        raw_name = (line.name or "").strip()
        raw_lines = [l.strip() for l in raw_name.splitlines() if l.strip()]

        product_label = (line.product_id.display_name or "").strip()

        if not product_label and raw_lines:
            product_label = raw_lines[0]

        inline_notes = []

        if raw_lines:
            first_line = raw_lines[0]
            if product_label and first_line == product_label:
                inline_notes = raw_lines[1:]
            elif product_label:
                inline_notes = raw_lines
            else:
                product_label = first_line
                inline_notes = raw_lines[1:]

        return product_label, inline_notes

    def _format_inline_notes(self, inline_notes):
        """
        Transforme les lignes techniques Odoo en texte lisible client.

        Exemple source :
        Nombre de coupes: Quantité: 2
        Longueur de coupe (en mètre): Dimension: 3
        Calcule quantité: Longueur totale coupée: 6
        Relicat: Chute:

        Exemple rendu :
        Découpe prévue :
        - 2 morceaux de 3 m
        - Longueur totale coupée : 6 m
        - Chute / reliquat : à calculer
        """
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
                formatted.append(f"- {cut_qty} morceaux de {self._format_meter_value(cut_length)}")
            elif cut_qty:
                formatted.append(f"- Nombre de morceaux : {cut_qty}")
            elif cut_length:
                formatted.append(f"- Longueur de coupe : {self._format_meter_value(cut_length)}")

            if total_length:
                formatted.append(
                    f"- Longueur totale coupée : {self._format_meter_value(total_length)}"
                )

            if has_relicat:
                formatted.append("- Chute / reliquat : à calculer")

        return formatted

    def _format_meter_value(self, value):
        """
        Formate une valeur en mètres pour éviter :
        3 -> 3 m
        3.5 -> 3,5 m
        3,5 -> 3,5 m
        """
        value = (value or "").strip().replace(",", ".")

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
