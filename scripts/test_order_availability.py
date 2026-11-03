"""Stale carts must not order archived, draft or missing products."""
import io
import json
from unittest.mock import patch
from openpyxl import load_workbook
from scripts import test_archives

server = test_archives.server


class OrderAvailabilityTests(test_archives.ArchiveTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for name, kind in [('order_no','TEXT'),('country','TEXT'),('product_total','REAL'),
                           ('total_weight','REAL'),('shipping_weight','REAL'),('shipping','REAL'),
                           ('total','REAL'),('created_at','INTEGER')]:
            cls.db.execute(f'ALTER TABLE orders ADD COLUMN {name} {kind}')
        cls.db.commit()

    def setUp(self):
        super().setUp()
        self.db.execute('DELETE FROM orders')
        self.db.commit()

    def test_stale_cart_rejected_for_every_unavailable_state(self):
        for product_id in ['archived','draft','missing']:
            for admin in [False,True]:
                status, result = self.api('/api/orders','POST',
                    dict(country='Europe',items=[dict(id=product_id,qty=1)]),admin=admin)
                self.assertEqual(status,400)
                self.assertIn('no longer available',result['error'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],0)

    def test_mixed_cart_is_not_partially_created(self):
        status,result = self.api('/api/orders','POST',dict(country='Europe',items=[
            dict(id='sample',qty=1),dict(id='archived',qty=1),dict(id='draft',qty=1)]))
        self.assertEqual(status,400)
        self.assertIn('no longer available',result['error'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],0)

    def test_archive_between_preparation_and_insert_is_rejected(self):
        items=[dict(id='sample',qty=1)]
        prepared=server.prepare_order_data(items,'Europe')
        self.db.execute("UPDATE products SET archived_at=1,published=0 WHERE id='sample'")
        self.db.commit()
        with patch.object(server,'prepare_order_data',return_value=prepared):
            with self.assertRaisesRegex(ValueError,'no longer available'):
                server.create_order_record(items,'Europe')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],0)

    def test_active_order_and_historical_export_remain_supported(self):
        order=server.create_order_record([dict(id='sample',qty=2)],'Europe')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],1)
        self.db.execute("UPDATE products SET archived_at=1,published=0 WHERE id='sample'")
        self.db.commit()
        stored=server.load_order_record(order['order_no'])
        self.assertEqual(stored['items'][0]['qty'],2)
        book=load_workbook(io.BytesIO(server.build_order_workbook_from_data(stored)))
        self.assertEqual(book['Order']['G5'].value,2)
        book.close()


if __name__=='__main__':
    import unittest
    unittest.main()
