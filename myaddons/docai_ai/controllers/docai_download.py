# docai_download.py


# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json


class DocaiDownloadController(http.Controller):

    @http.route('/docai/download/<int:move_id>/<string:kind>', type='http', auth='user')
    def download_json(self, move_id, kind="min", **kwargs):
        """
        Télécharge le JSON d'une facture
        - kind = "raw" → JSON complet
        - kind = "min" → JSON simplifié
        """
        move = request.env['account.move'].browse(move_id)
        if not move.exists():
            return request.not_found()

        content = move.docai_json_raw if kind == "raw" else move.docai_json
        if not content:
            return request.not_found()

        filename = f"facture_{move.id}_{kind}.json"

        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/json'),
                ('Content-Disposition', f'attachment; filename={filename}')
            ]
        )
