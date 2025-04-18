# models/website.py
import requests
from bs4 import BeautifulSoup
from odoo import models, fields, tools
print(">>> MODULE website_link_checker.models.website CHARGÉ <<<")
class Website(models.Model):
    _inherit = 'website'

    link_checker_user_id = fields.Many2one(
        'res.users',
        string="Destinataire des rapports de liens cassés"
    )

    def run_link_checker(self):
        for website in self.search([]):
            domain = website.domain.strip('/')
            sitemap_url = f'https://{domain}/sitemap.xml'
            errors = website._parse_sitemap_and_check(sitemap_url)

            if errors:
                user = website.link_checker_user_id or website.env.ref('base.user_admin')
                body = website._format_report(errors)
                website.env['mail.message'].create({
                    'subject': f'Erreurs détectées sur {domain}',
                    'body': body,
                    'model': 'res.users',
                    'res_id': user.id,
                    'message_type': 'notification',
                    'subtype_id': website.env.ref('mail.mt_note').id,
                })

    def _parse_sitemap_and_check(self, sitemap_url):
        errors = {}
        try:
            r = requests.get(sitemap_url, timeout=10)
            if r.status_code != 200:
                return {sitemap_url: f"Sitemap inaccessible ({r.status_code})"}
            soup = BeautifulSoup(r.content, 'xml')
            if soup.find('sitemapindex'):
                for sm in soup.find_all('loc'):
                    errors.update(self._parse_sitemap_and_check(sm.text.strip()))
            else:
                for loc in soup.find_all('loc'):
                    url = loc.text.strip()
                    res = requests.get(url, timeout=10)
                    if res.status_code >= 400:
                        errors[url] = f"Page inaccessible ({res.status_code})"
                    else:
                        sub_errors = self._check_links_in_page(url, res.text)
                        if sub_errors:
                            errors[url] = sub_errors
        except Exception as e:
            errors[sitemap_url] = str(e)
        return errors

    def _check_links_in_page(self, url, html):
        page_errors = []
        soup = BeautifulSoup(html, 'html.parser')

        for link in soup.find_all('a', href=True):
            link_url = link['href']
            if link_url.startswith('http'):
                try:
                    r = requests.get(link_url, timeout=5)
                    if r.status_code >= 400:
                        page_errors.append(f"Lien cassé : {link_url} ({r.status_code})")
                except Exception as e:
                    page_errors.append(f"Lien cassé : {link_url} (erreur : {e})")

        if not soup.find('title'):
            page_errors.append("Balise <title> manquante")

        if not soup.find('meta', attrs={'name': 'description'}):
            page_errors.append("Balise <meta name='description'> manquante")

        for img in soup.find_all('img', src=True):
            img_url = img['src']
            if img_url.startswith('http'):
                try:
                    r = requests.get(img_url, timeout=5)
                    if r.status_code >= 400:
                        page_errors.append(f"Image cassée : {img_url} ({r.status_code})")
                except Exception as e:
                    page_errors.append(f"Image cassée : {img_url} (erreur : {e})")

        return page_errors

    def _format_report(self, errors):
        report = "<h3>Rapport de vérification des liens</h3><ul>"
        for page, issues in errors.items():
            report += f"<li><b>{page}</b><ul>"
            if isinstance(issues, list):
                for issue in issues:
                    report += f"<li>{tools.html_escape(issue)}</li>"
            else:
                report += f"<li>{tools.html_escape(issues)}</li>"
            report += "</ul></li>"
        report += "</ul>"
        return report
