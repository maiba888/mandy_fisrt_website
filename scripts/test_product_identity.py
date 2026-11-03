"""Stable product identity across API, order preparation and Excel grouping."""
import io
from unittest.mock import patch
from openpyxl import load_workbook
from scripts import test_archives

server = test_archives.server


class ProductIdentityTests(test_archives.ArchiveTests):
    def test_create_without_sku_and_preserve_identity_on_edit(self):
        payload = dict(brand='Brand', name='Product', price=3.68, weight=.1, colors=['01'])
        status, result = self.api('/api/products', 'POST', payload, admin=True)
        self.assertEqual(status, 200)
        first = result['id']
        second = self.api('/api/products', 'POST', payload, admin=True)[1]['id']
        self.assertNotEqual(first, second)
        before = dict(self.db.execute('SELECT id,sku FROM products WHERE id=?', (first,)).fetchone())
        self.assertEqual(self.api('/api/products/'+first, 'PUT', payload, admin=True)[0], 200)
        after = dict(self.db.execute('SELECT id,sku FROM products WHERE id=?', (first,)).fetchone())
        self.assertEqual(before, after)

    def test_order_ids_with_duplicate_sku_are_independent(self):
        products = {
            'one': dict(id='one', sku='RD-2', name='Eye patches', brand='rhode', price=3.68, weight=.1),
            'two': dict(id='two', sku='RD-2', name='Lip set', brand='rhode', price=4.2, weight=.2, colors=['lip set']),
        }
        with patch.object(server, 'products_by_id', return_value=products):
            order = server.prepare_order_data([dict(id='one',sku='RD-2',qty=5,color='default'),
                dict(id='two',sku='RD-2',qty=5,color='lip set')], 'Europe')
        self.assertEqual([p['id'] for p in order['items']], ['one','two'])
        self.assertEqual([p['qty'] for p in order['items']], [5,5])
        self.assertEqual(order['product_total'], 39.4)
        self.assertEqual(len(server.normalize_order_items([dict(id='one',sku='x',qty=2),dict(id='one',sku='y',qty=3)])),1)

    def test_excel_groups_shades_only_within_product_id(self):
        common = dict(brand='Brand',name='Identical name',price=4,weight=.1,qty=5,image='')
        items = [dict(common,id='one',color='01'),dict(common,id='two',color='02'),dict(common,id='one',color='03')]
        book = load_workbook(io.BytesIO(server.build_order_workbook_from_data({'items':items,'country':'Europe'})))
        sheet = book['Order']
        self.assertEqual(sheet['G2'].value,10)
        self.assertEqual(sheet['E2'].value,'01\n03')
        self.assertEqual(sheet['G3'].value,5)
        self.assertEqual(sheet['E3'].value,'02')
        self.assertEqual(sheet['C2'].value,sheet['C3'].value)
        book.close()


if __name__ == '__main__':
    import unittest
    unittest.main()
