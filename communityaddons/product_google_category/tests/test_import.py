from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestProductGoogleCategory(TransactionCase):

    def setUp(self):
        super(TestProductGoogleCategory, self).setUp()
        self.google_category = self.env['product.google.category']
        self.user = self.env.ref('base.user_demo')

    def test_import_from_url(self):
        wizard = self.env['base_import.helper'].with_user(self.user).create({
            'mode': 'google_categ',
            'url': 'https://www.google.com/basepages/producttype/taxonomy-with-ids.en-US.txt',
        })

        result = wizard.open_url(wizard.url)
        self.assertEqual(result['error'], None)

        wizard.with_user(self.user).action_import()

        self.assertEqual(
            self.google_category.search_count([]),
            len(result['content'].split('\n')) - 2,  # Exclude the 1st and the last lines
        )
