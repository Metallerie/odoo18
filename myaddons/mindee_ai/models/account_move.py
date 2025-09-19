# -*- coding: utf-8 -*-
import base64
import os
import tempfile
import logging
from odoo import models, fields

# --- Mindee v2 (MLA) ---
from mindee import ClientV2, InferenceParameters, PathInput  # v2 SDK :contentReference[oaicite:2]{index=2}

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'
    mindee_local_response = fields.Text(string="Réponse OCR (Mindee)", readonly=True)
    pdf_attachment_id = fields.Many2one('ir.attachment', string="PDF OCR")
    show_pdf_button = fields.Boolean(compute='_compute_show_pdf_button', store=True)

    def _compute_show_pdf_button(self):
        for move in self:
            move.show_pdf_button = bool(move.pdf_attachment_id)

    def action_open_pdf_viewer(self):
        self.ensure_one()
        if self.pdf_attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{self.pdf_attachment_id.id}?download=false',
                'target': 'new',
            }
        return False

    # --- Helpers v2 ---
    @staticmethod
    def _m_field(fields_dict, key, default=None):
        fld = fields_dict.get(key)
        return getattr(fld, "value", default) if fld is not None else default

    @staticmethod
    def _m_items(fields_dict, key):
        fld = fields_dict.get(key)
        return getattr(fld, "items", []) if fld is not None else []

    def _write_tmp_from_attachment(self, attachment):
        """Écrit la PJ (base64) en fichier temp et renvoie le chemin."""
        try:
            raw = base64.b64decode(attachment.datas or b"")
            suffix = ""
            name = (attachment.display_name or "document.pdf").lower()
            if name.endswith(".pdf"):
                suffix = ".pdf"
            elif name.endswith(".jpg") or name.endswith(".jpeg"):
                suffix = ".jpg"
            elif name.endswith(".png"):
                suffix = ".png"
            else:
                suffix = ".pdf"
            fd, tmp_path = tempfile.mkstemp(prefix=f"mindee_{attachment.id}_", suffix=suffix)
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
            return tmp_path
        except Exception as e:
            _logger.error(f"Impossible d'écrire le fichier temporaire pour {attachment.display_name}: {e}")
            return None

    def action_ocr_fetch(self):
        ICP = self.env['ir.config_parameter'].sudo()
        api_key = ICP.get_param('mindee_ai.mindee_api_key')
        model_id = ICP.get_param('mindee_ai.model_id')  # ← mets l’ID de ton modèle (Invoice / Workflow)
        if not api_key or not model_id:
            _logger.error("Clé API Mindee ou Model ID manquant (mindee_ai.mindee_api_key / mindee_ai.model_id).")
            return False

        try:
            mindee_client = ClientV2(api_key)  # MLA v2 client :contentReference[oaicite:3]{index=3}
        except Exception as e:
            _logger.error(f"Init Mindee ClientV2 KO: {e}")
            return False

        params = InferenceParameters(model_id=model_id)  # options: rag/raw_text/polygon/confidence… :contentReference[oaicite:4]{index=4}

        # Produit Éco-part (comme avant)
        template = self.env['product.template'].browse(30)
        if not template.exists():
            _logger.warning("Template produit Éco-part ID 30 introuvable.")
            return False
        ecotax_product = template.product_variant_id
        if not ecotax_product:
            _logger.warning("Aucune variante pour le produit Éco-part.")
            return False

        for move in self:
            for message in move.message_ids:
                for attachment in message.attachment_ids:
                    if "pdf" not in (attachment.display_name or "").lower():
                        continue

                    tmp_path = self._write_tmp_from_attachment(attachment)
                    if not tmp_path:
                        continue

                    try:
                        input_src = PathInput(tmp_path)  # on envoie un fichier local :contentReference[oaicite:5]{index=5}
                        resp = mindee_client.enqueue_and_get_inference(input_src, params)  # polling v2 :contentReference[oaicite:6]{index=6}
                    except Exception as e:
                        _logger.error(f"Mindee v2 erreur pour {attachment.display_name}: {e}")
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
                        continue
                    finally:
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass

                    # garde le PDF lié pour bouton d’aperçu
                    move.pdf_attachment_id = attachment

                    # --- Lecture des champs v2 ---
                    # resp.inference.result.fields => dict de champs (simples/objets/listes) :contentReference[oaicite:7]{index=7}
                    fields_dict = getattr(getattr(resp, "inference", None), "result", None)
                    fields_dict = getattr(fields_dict, "fields", {}) if fields_dict else {}

                    partner_name = self._m_field(fields_dict, "supplier_name", "Nom Inconnu") or "Nom Inconnu"
                    partner_addr = self._m_field(fields_dict, "supplier_address", None)

                    partner = self.env['res.partner'].search([("name", "ilike", partner_name)], limit=1)
                    if not partner:
                        partner_vals = {"name": partner_name}
                        if partner_addr:
                            partner_vals["street"] = partner_addr
                        partner = self.env['res.partner'].create(partner_vals)

                    line_ids = []
                    total_calculated_net = 0.0
                    total_calculated_tax = 0.0  # on ne recalcule pas finement TVA ici (Odoo gère via taxes)

                    # Lignes: liste d'objets 'line_items' avec sous-champs: description, unit_price, quantity, product_code, unit_measure…
                    for obj in self._m_items(fields_dict, "line_items"):
                        sub = getattr(obj, "fields", {})  # objet -> sous-fields
                        description = getattr(sub.get("description"), "value", None) or "Sans description"
                        unit_price = float(getattr(sub.get("unit_price"), "value", 0.0) or 0.0)
                        quantity = float(getattr(sub.get("quantity"), "value", 1.0) or 1.0)
                        product_code = getattr(sub.get("product_code"), "value", None)
                        unit_measure = (getattr(sub.get("unit_measure"), "value", "") or "").lower()

                        product_id = False
                        if product_code:
                            product_id = self.env['product.product'].search(
                                [('default_code', '=', product_code)], limit=1
                            )
                        if not product_id:
                            product_id = self.env['product.product'].search(
                                [('name', 'ilike', description)], limit=1
                            )
                        if not product_id:
                            product_id = self.env['product.product'].create({
                                'name': description,
                                'type': 'consu',
                                'list_price': unit_price,
                                'purchase_ok': True,
                                'sale_ok': False,
                                'default_code': product_code or f"{description[:10].upper()}",
                            })
                            _logger.info(f"Produit créé : {description} (ref {product_code or 'auto'})")

                        line_net = unit_price * quantity
                        total_calculated_net += line_net

                        line_data = {
                            "name": description,
                            "product_id": product_id.id,
                            "price_unit": unit_price,
                            "quantity": quantity,
                            "tax_ids": [(6, 0, product_id.supplier_taxes_id.ids)],
                        }
                        line_ids.append((0, 0, line_data))

                        # Supplierinfo (liée au partenaire)
                        supplierinfo_domain = [('partner_id', '=', partner.id)]
                        supplierinfo_vals = {
                            'partner_id': partner.id,
                            'min_qty': 1,
                            'price': unit_price,
                            'product_code': product_code or product_id.default_code,
                            'product_name': description,
                            'product_uom': product_id.uom_po_id.id,
                            'delay': 1,
                        }
                        if product_id.product_tmpl_id.product_variant_count > 1:
                            supplierinfo_domain.append(('product_id', '=', product_id.id))
                            supplierinfo_vals['product_id'] = product_id.id
                        else:
                            supplierinfo_domain.append(('product_tmpl_id', '=', product_id.product_tmpl_id.id))
                            supplierinfo_vals['product_tmpl_id'] = product_id.product_tmpl_id.id

                        supplierinfo = self.env['product.supplierinfo'].search(supplierinfo_domain, limit=1)
                        if supplierinfo:
                            supplierinfo.write(supplierinfo_vals)
                        else:
                            self.env['product.supplierinfo'].create(supplierinfo_vals)

                        # Éco-part pondérée au poids si nécessaire
                        has_ecopart_tax = any(tax.amount_type == 'fixed' for tax in product_id.supplier_taxes_id)
                        if has_ecopart_tax:
                            if unit_measure == 'kg':
                                weight_kg = quantity
                            elif product_id.weight:
                                weight_kg = product_id.weight * quantity
                            else:
                                weight_kg = 0.0
                            if weight_kg > 0:
                                ecotax_line = {
                                    "name": f"Éco-part pour {description}",
                                    "product_id": ecotax_product.id,
                                    "quantity": weight_kg,
                                    "price_unit": ecotax_product.standard_price,
                                    "tax_ids": [(6, 0, ecotax_product.supplier_taxes_id.ids)],
                                }
                                line_ids.append((0, 0, ecotax_line))

                    # Totaux (issus du doc)
                    document_total_net = float(self._m_field(fields_dict, "total_net", 0.0) or 0.0)
                    document_total_amount = float(self._m_field(fields_dict, "total_amount", 0.0) or 0.0)
                    document_total_tax = float(self._m_field(fields_dict, "total_tax", 0.0) or 0.0)
                    total_calculated_amount = total_calculated_net + total_calculated_tax

                    if (abs(document_total_net - total_calculated_net) > 0.01 or
                        abs(document_total_tax - total_calculated_tax) > 0.01 or
                        abs(document_total_amount - total_calculated_amount) > 0.01):
                        _logger.warning(
                            f"Totaux différents sur {move.name} : "
                            f"net(doc)={document_total_net} vs calc={total_calculated_net} | "
                            f"tax(doc)={document_total_tax} vs calc={total_calculated_tax} | "
                            f"ttc(doc)={document_total_amount} vs calc={total_calculated_amount}"
                        )

                    move.write({
                        "partner_id": partner.id,
                        "invoice_date": self._m_field(fields_dict, "date"),
                        "invoice_date_due": self._m_field(fields_dict, "due_date"),
                        "ref": self._m_field(fields_dict, "invoice_number", "Référence inconnue"),
                        "invoice_line_ids": line_ids,
                    })

        return True
