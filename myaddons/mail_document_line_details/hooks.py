from odoo import api, SUPERUSER_ID


DETAIL_BLOCK = '<t t-out="object._get_mail_line_details_html()"/>'

ANCHORS = [
    "Pourriez-vous confirmer la bonne réception de cette commande ?",
    "Could you please confirm receipt of this order?",
]


def _get_env(cr):
    return api.Environment(cr, SUPERUSER_ID, {})


def post_init_hook(env_or_cr):
    if hasattr(env_or_cr, "cr"):
        env = env_or_cr
    else:
        env = _get_env(env_or_cr)

    template = env.ref("purchase.email_template_edi_purchase", raise_if_not_found=False)
    if not template or not template.body_html:
        return

    body = template.body_html

    if DETAIL_BLOCK in body:
        return

    for anchor in ANCHORS:
        if anchor in body:
            body = body.replace(anchor, DETAIL_BLOCK + "<br/><br/>" + anchor, 1)
            template.write({"body_html": body})
            return


def uninstall_hook(env_or_cr):
    if hasattr(env_or_cr, "cr"):
        env = env_or_cr
    else:
        env = _get_env(env_or_cr)

    template = env.ref("purchase.email_template_edi_purchase", raise_if_not_found=False)
    if not template or not template.body_html:
        return

    body = template.body_html
    body = body.replace(DETAIL_BLOCK + "<br/><br/>", "")
    body = body.replace(DETAIL_BLOCK, "")
    template.write({"body_html": body})
