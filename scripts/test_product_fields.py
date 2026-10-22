"""Product API round trips retain complete fields, using an isolated database."""
from scripts import test_archives


class ProductFieldTests(test_archives.ArchiveTests):
    def test_long_fields_and_many_shades_round_trip(self):
        product = dict(self.api('/api/products', admin=True)[1]['products'][0])
        shades = [f'{index:03d} Garnet - Shade' for index in range(1, 1001)]
        product.update(colors=shades, brand='Brand' * 200, name='Name' * 300,
                       category='Category' * 100, sku='SKU' * 100,
                       description=('Product information. ' * 3000).strip(),
                       images=[f'/src/assets/uploads/image-{i}.jpg' for i in range(100)])
        product['image'] = product['images'][0]
        status, _ = self.api('/api/products/sample', 'PUT', product, admin=True)
        self.assertEqual(status, 200)
        saved = next(p for p in self.api('/api/products', admin=True)[1]['products'] if p['id'] == 'sample')
        for field in ['colors', 'brand', 'name', 'category', 'sku', 'description', 'images']:
            self.assertEqual(saved[field], product[field], field)
        self.assertEqual(self.db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')


if __name__ == '__main__':
    import unittest
    unittest.main()
