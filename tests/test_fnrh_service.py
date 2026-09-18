import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
import fnrh_service as service
import reservations


class DurableFnrhTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.sqlite'
        reservations.init_schema(self.connection)
        service.init_schema(self.connection)
        with self.connection() as db:
            db.execute('''INSERT INTO reservations(id,external_id,guest_name,phone,cpf,arrival,departure,
                pre_status,checkin_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                ('r1', 'FAKE-001', 'Hospede Ficticio', '5511000000000', '52998224725',
                 '2030-01-01', '2030-01-03', 'PRE_CHECKIN_CONCLUIDO', 'CHECK_IN_REALIZADO', 'now', 'now'))

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def send(self, **kwargs):
        body = dict(action='simulate', reservation_id='r1', operation='checkin', human_checked=True, outcome='ok')
        body.update(kwargs)
        return service.change(self.connection, body, 'test-operator')['job']

    def edit(self, column, value):
        with self.connection() as db:
            db.execute(f'UPDATE reservations SET {column}=? WHERE id=?', (value, 'r1'))

    def test_restart_and_parallel_idempotency(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: self.send(), range(12)))
        self.assertEqual({r['id'] for r in results}, {results[0]['id']})
        service.init_schema(self.connection)
        self.assertEqual(self.send()['attempts'], 1)
        self.assertEqual(len(self.send()['history']), 1)

    def test_uncertainty_requires_human_reconciliation(self):
        job = self.send(outcome='uncertain')
        for outcome in ('ok', 'error', 'uncertain'):
            with self.assertRaises(ValueError):
                self.send(outcome=outcome)
        for changes in ({'human_checked': False}, {'reason': ''}, {'job_id': 999}, {'resolution': 'invented'}):
            args = dict(action='reconcile', job_id=job['id'], resolution='not_sent', reason='Conferencia ficticia')
            args.update(changes)
            with self.assertRaises(ValueError):
                self.send(**args)
        reconciled = self.send(action='reconcile', job_id=job['id'], resolution='not_sent', reason='Conferencia ficticia')
        self.assertEqual(reconciled['state'], 'SIMULATED_NOT_SENT')
        self.assertEqual(self.send()['attempts'], 2)

    def test_confirmed_is_final_and_audited(self):
        job = self.send(outcome='uncertain')
        job = self.send(action='reconcile', job_id=job['id'], resolution='confirmed', reason='Resultado ficticio conferido')
        self.assertEqual(job['state'], 'SIMULATED_OK')
        self.assertEqual(self.send()['attempts'], 1)
        with self.assertRaises(ValueError):
            self.send(action='reconcile', job_id=job['id'], resolution='confirmed', reason='Duplicado')
        with self.connection() as db:
            reason, actor, stamp = db.execute("SELECT reason,actor,created_at FROM fnrh_events WHERE action='reconcile_confirmed'").fetchone()
        self.assertEqual(reason, 'Resultado ficticio conferido')
        self.assertEqual(actor, 'test-operator')
        self.assertTrue(stamp)

    def test_checkout_order_and_identity(self):
        self.edit('checkout_status', 'CHECK_OUT_REALIZADO')
        with self.assertRaises(ValueError):
            self.send(operation='checkout')
        self.send()
        self.edit('room', '202')
        with self.assertRaises(ValueError):
            self.send(operation='checkout')
        self.edit('room', None)
        self.assertEqual(self.send(operation='checkout')['state'], 'SIMULATED_OK')

    def test_checkout_transition_preserves_checkin_receipt(self):
        self.send()
        self.edit('checkout_status', 'CHECK_OUT_REALIZADO')
        self.assertEqual(self.send()['attempts'], 1)
        self.assertEqual(self.send(operation='checkout')['state'], 'SIMULATED_OK')
        self.assertNotIn('LOCAL_DATA_CHANGED', service.overview(self.connection)['reservations'][0]['pending'])

    def test_changed_snapshot_blocks_even_after_reconciliation(self):
        job = self.send(outcome='uncertain')
        self.edit('guest_name', 'Outro Ficticio')
        self.send(action='reconcile', job_id=job['id'], resolution='not_sent', reason='Verificacao ficticia')
        with self.assertRaises(ValueError):
            self.send()
        self.assertIn('LOCAL_DATA_CHANGED', service.overview(self.connection)['reservations'][0]['pending'])

    def test_privacy_and_readonly_reservations(self):
        with self.connection() as db:
            before = db.execute('SELECT * FROM reservations').fetchall()
        job = self.send(outcome='uncertain')
        self.send(action='reconcile', job_id=job['id'], resolution='confirmed', reason='Razao privada')
        result = service.overview(self.connection)
        self.assertEqual(result['mode'], 'simulation')
        self.assertFalse(result['official_enabled'])
        encoded = json.dumps(result)
        for value in ('52998224725', '5511000000000', 'Razao privada', 'snapshot', 'identity'):
            self.assertNotIn(value, encoded)
        with self.connection() as db:
            self.assertEqual(before, db.execute('SELECT * FROM reservations').fetchall())

    def test_adversarial_json_inputs_fail_cleanly(self):
        for field in ('outcome', 'operation', 'action', 'reservation_id'):
            for value in ({}, [], None, 17):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        self.send(**{field: value})
        with self.assertRaises(ValueError):
            service.change(self.connection, [], 'operator')
        self.assertEqual(service.overview(self.connection)['reservations'][0]['jobs'], [])

    def test_invalid_local_data_and_failed_retry(self):
        for checked in (False, 1, 'true'):
            with self.assertRaises(ValueError):
                self.send(human_checked=checked)
        self.edit('cpf', '123')
        with self.assertRaises(ValueError):
            self.send()
        self.edit('cpf', '52998224725')
        self.assertEqual(self.send(outcome='error')['state'], 'SIMULATED_ERROR')
        self.assertEqual(self.send()['attempts'], 2)


if __name__ == '__main__':
    unittest.main()

