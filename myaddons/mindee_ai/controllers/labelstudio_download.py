from odoo.http import content_disposition, request, route, Controller


class LabelStudioDownloadController(Controller):

    @route('/mindee/labelstudio/download/<string:doc_type>/<int:history_id>',
           type='http', auth='user')
    def download_labelstudio(self, doc_type, history_id, **kwargs):
        history = request.env['mindee.labelstudio.history'].sudo().browse(history_id)
        if not history.exists():
            return request.not_found()

        if doc_type == "json":
            content = history.json_content or ""
            filename = f"labelstudio_history_{history.id}.json"
        else:
            content = history.xml_content or ""
            filename = f"labelstudio_history_{history.id}.xml"

        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/octet-stream'),
                ('Content-Disposition', content_disposition(filename))
            ]
        )
