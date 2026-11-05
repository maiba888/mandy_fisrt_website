"""Archive visibility, authentication and restore tests with synthetic data."""
import http.client
import json
from unittest.mock import patch
import unittest

from scripts import test_seo
server = test_seo.server


class ArchiveTests(test_seo.SeoTests):
    def api(self, path, method='GET', payload=None, admin=False):
        with patch.object(server.CatalogHandler, 'current_user', return_value='admin' if admin else None):
            client = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=5)
            client.request(method, path, body=json.dumps(payload) if payload is not None else None,
                           headers={'Content-Type': 'application/json'})
            response = client.getresponse()
            result = response.status, json.loads(response.read())
            client.close()
            return result

    def test_archives_and_drafts_are_admin_only(self):
        query = '/api/products?include_archived=1&include_drafts=1'
        self.assertEqual([p['id'] for p in self.api(query)[1]['products']], ['sample'])
        self.assertEqual({p['id'] for p in self.api(query, admin=True)[1]['products']}, {'sample', 'draft', 'archived'})
        self.assertEqual({p['id'] for p in self.api('/api/products?include_drafts=1', admin=True)[1]['products']}, {'sample', 'draft'})

    def test_restore_requires_login_and_preserves_product(self):
        self.db.execute("UPDATE products SET first_published_at=100 WHERE id='archived'")
        self.db.commit()
        before = dict(self.db.execute("SELECT * FROM products WHERE id='archived'").fetchone())
        self.assertEqual(self.api('/api/products/archived/restore', 'POST', {}, admin=False)[0], 401)
        self.assertEqual(self.api('/api/products/archived/restore', 'POST', {}, admin=True)[0], 200)
        after = dict(self.db.execute("SELECT * FROM products WHERE id='archived'").fetchone())
        self.assertEqual(after['archived_at'], 0)
        self.assertEqual(after['published'], 1)
        for field in ['id', 'sku', 'brand', 'name', 'price', 'weight', 'image', 'images_json', 'colors_json', 'first_published_at']:
            self.assertEqual(before[field], after[field], field)
        self.assertEqual(self.request('/product/archived')[0], 200)
        self.assertIn('/product/archived', self.request('/sitemap.xml')[2])
        self.assertEqual(self.api('/api/products/missing/restore', 'POST', {}, admin=True)[0], 404)

    def test_archive_and_edit_do_not_delete_or_republish(self):
        self.assertEqual(self.api('/api/products/sample', 'DELETE', admin=True)[0], 200)
        self.assertEqual(self.request('/product/sample')[0], 404)
        product = server.product_from_row(self.db.execute("SELECT * FROM products WHERE id='sample'").fetchone())
        product.update(name='Edited archive', published=True, archived_at=0)
        self.assertEqual(self.api('/api/products/sample', 'PUT', product, admin=True)[0], 200)
        stored = self.db.execute("SELECT * FROM products WHERE id='sample'").fetchone()
        self.assertGreater(stored['archived_at'], 0)
        self.assertEqual(stored['published'], 0)
        self.assertEqual(stored['name'], 'Edited archive')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM products').fetchone()[0], 3)


if __name__ == '__main__':
    unittest.main()
