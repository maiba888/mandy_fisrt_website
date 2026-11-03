"""Order and admin mutations validate current data without changing history."""
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch
from scripts.test_order_availability import OrderAvailabilityTests, server


class OrderValidationTests(OrderAvailabilityTests):
    def assert_no_orders(self):
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 0)

    def test_deleted_shades_rejected_but_spaces_and_hyphens_literal(self):
        for shade in ['deleted', 'warm', 'pink', 'Default']:
            status, result = self.api('/api/orders', 'POST', dict(country='Europe',
                items=[dict(id='sample', qty=1, color=shade)]))
            self.assertEqual(status, 400)
            self.assertIn('Shade/type', result['error'])
        self.assert_no_orders()
        self.db.execute("UPDATE products SET colors_json=? WHERE id='sample'",
                        (json.dumps(['01', 'warm pink', '1-2-3']),))
        self.db.commit()
        order = server.create_order_record([dict(id='sample', qty=2, color='warm pink'),
                                           dict(id='sample', qty=3, color='1-2-3')], 'Europe')
        self.assertEqual([p['color'] for p in order['items']], ['warm pink', '1-2-3'])

    def test_bad_quantities_and_malformed_lines_never_silently_change(self):
        for qty in [0, -1, 1.5, True, None, 'NaN', 'Infinity', 'no', [], 9007199254740992]:
            status, _ = self.api('/api/orders', 'POST', dict(items=[dict(id='sample', qty=qty, color='01')]))
            self.assertEqual(status, 400, repr(qty))
        for item in [None, [], 'sample', {}, dict(qty=1)]:
            status, _ = self.api('/api/orders', 'POST', dict(items=[dict(id='sample', qty=1, color='01'), item]))
            self.assertEqual(status, 400, repr(item))
        self.assert_no_orders()

    def test_prices_and_weights_are_server_owned_and_read_under_lock(self):
        self.db.execute("UPDATE products SET price=7.5,weight=.3 WHERE id='sample'")
        self.db.commit()
        original = server.prepare_order_data
        def prepare(*args, **kwargs):
            self.assertIs(kwargs['conn'], self.db)
            self.assertTrue(self.db.in_transaction)
            return original(*args, **kwargs)
        with patch.object(server, 'prepare_order_data', side_effect=prepare):
            order = server.create_order_record([dict(id='sample', qty=2, color='01', price=.01, weight=.001)], 'Europe')
        self.assertEqual(order['product_total'], 15)
        self.assertEqual(order['total_weight'], .6)
        self.assertEqual(order['shipping'], 31.2)
        self.assertEqual(server.load_order_record(order['order_no'])['items'][0]['price'], 7.5)

    def test_order_does_not_accept_invalid_stored_price_or_weight(self):
        for field in ['price', 'weight']:
            for value in [0, -1, float('inf')]:
                self.db.execute(f"UPDATE products SET {field}=? WHERE id='sample'", (value,))
                self.db.commit()
                with self.assertRaises(ValueError):
                    server.create_order_record([dict(id='sample', qty=1, color='01')], 'Europe')
            self.db.execute(f"UPDATE products SET {field}=? WHERE id='sample'", (5.25 if field=='price' else .1,))
            self.db.commit()
        self.assert_no_orders()

    def test_admin_validation_is_not_browser_only(self):
        product = server.product_from_row(self.db.execute("SELECT * FROM products WHERE id='sample'").fetchone())
        for changes in [dict(price=0), dict(weight=-1), dict(price='NaN'), dict(weight='Infinity'),
                        dict(brand=''), dict(name=''), dict(colors=[]), dict(colors=' / '), dict(published='false')]:
            for method, path in [('POST', '/api/products'), ('PUT', '/api/products/sample')]:
                status, _ = self.api(path, method, dict(product, **changes), admin=True)
                self.assertEqual(status, 400, (method, changes))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM products').fetchone()[0], 3)
        self.assertEqual(self.db.execute("SELECT price FROM products WHERE id='sample'").fetchone()[0], 5.25)

    def test_admin_edit_locks_before_reading_status_and_preserves_identity(self):
        product = server.product_from_row(self.db.execute("SELECT * FROM products WHERE id='sample'").fetchone())
        statements = []
        self.db.set_trace_callback(statements.append)
        try:
            status, _ = self.api('/api/products/sample', 'PUT', dict(product, sku='tampered'), admin=True)
        finally:
            self.db.set_trace_callback(None)
        self.assertEqual(status, 200)
        lock = next(i for i, sql in enumerate(statements) if 'BEGIN IMMEDIATE' in sql)
        read = next(i for i, sql in enumerate(statements) if 'SELECT archived_at, sku' in sql)
        self.assertLess(lock, read)
        self.assertEqual(self.db.execute("SELECT sku FROM products WHERE id='sample'").fetchone()[0], 'sample')

    def test_legacy_description_shades_match_frontend_fallback(self):
        self.assertEqual(server.product_shades(dict(colors=[], description='Colors:001/warm pink/1-2 Size:5cm')), ['001','warm pink','1-2'])
        self.assertEqual(server.product_shades(dict(colors=['02'], description='Colors:001')), ['02'])
        self.assertEqual(server.product_shades({}), ['Default'])

    def test_non_object_api_payloads_are_bad_requests(self):
        for body in [[], 'not an object', 12]:
            self.assertEqual(self.api('/api/orders', 'POST', body)[0], 400)
            self.assertEqual(self.api('/api/products', 'POST', body, admin=True)[0], 400)
        self.assert_no_orders()

    def test_concurrent_catalog_writer_cannot_change_prepared_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'isolated.sqlite3'
            first = sqlite3.connect(path)
            first.row_factory = sqlite3.Row
            self.db.backup(first)
            second = sqlite3.connect(path, timeout=0)
            original = server.products_by_id
            def read(*args, **kwargs):
                result = original(*args, **kwargs)
                with self.assertRaisesRegex(sqlite3.OperationalError, 'locked'):
                    second.execute("UPDATE products SET price=99,colors_json='[]',archived_at=1 WHERE id='sample'")
                second.rollback()
                return result
            try:
                with patch.object(server, 'connect', return_value=first), \
                     patch.object(server, 'products_by_id', side_effect=read):
                    order = server.create_order_record([dict(id='sample', qty=2, color='01')], 'Europe')
                self.assertEqual(order['product_total'], 10.5)
                second.execute("UPDATE products SET price=99 WHERE id='sample'")
                second.commit()
                self.assertEqual(json.loads(first.execute('SELECT items_json FROM orders').fetchone()[0])[0]['price'], 5.25)
            finally:
                second.close()
                first.close()

    def test_legacy_excel_generation_also_rejects_removed_shades(self):
        status, _ = self.api('/api/orders/excel', 'POST',
                             dict(items=[dict(id='sample', qty=1, color='deleted')]), admin=True)
        self.assertEqual(status, 400)
        self.assert_no_orders()


if __name__ == '__main__':
    import unittest
    unittest.main()
