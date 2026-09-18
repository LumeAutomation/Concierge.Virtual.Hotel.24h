import json
import unittest
from unittest.mock import patch
from fnrh import Simulator, SimulationBlocked
from scripts.simulate_fnrh import run


class FnrhSimulationTests(unittest.TestCase):
    def setUp(self):
        self.reservation = dict(external_id='FAKE-001', guest_name='Hospede Ficticio',
                                cpf='52998224725', phone='5511000000000',
                                arrival='2030-01-01', departure='2030-01-03',
                                pre_status='PRE_CHECKIN_CONCLUIDO',
                                checkin_status='CHECK_IN_REALIZADO', checkout_status='PENDENTE')
        self.simulator = Simulator()

    def prepare(self, operation='checkin', **changes):
        return self.simulator.prepare(dict(self.reservation, **changes), operation, human_checked=True)

    def test_pending_validation_and_human_gate(self):
        for change in (dict(cpf='123'), dict(arrival=None), dict(departure='2029-01-01'),
                       dict(pre_status='PRE_CHECKIN_PENDENTE'), dict(phone='invalid')):
            with self.subTest(change=tuple(change)):
                self.assertTrue(self.simulator.inspect(dict(self.reservation, **change)))
                with self.assertRaises(SimulationBlocked):
                    self.prepare(**change)
        for checked in (False, 1, 'yes'):
            with self.assertRaises(SimulationBlocked):
                self.simulator.prepare(self.reservation, 'checkin', human_checked=checked)

    def test_order_and_local_reception_states(self):
        with self.assertRaises(SimulationBlocked):
            self.prepare(checkin_status='PENDENTE')
        with self.assertRaises(SimulationBlocked):
            self.prepare('checkout', checkout_status='CHECK_OUT_REALIZADO')
        self.prepare()
        with self.assertRaises(SimulationBlocked):
            self.prepare('checkout', checkout_status='CHECK_OUT_REALIZADO')
        self.simulator.execute(self.reservation, 'checkin')
        with self.assertRaises(SimulationBlocked):
            self.prepare('checkout')
        self.reservation['checkout_status'] = 'CHECK_OUT_REALIZADO'
        self.prepare('checkout')
        self.assertEqual(self.simulator.execute(self.reservation, 'checkout').state, 'SIMULATED_OK')

    def test_idempotency_and_changed_data(self):
        self.prepare()
        result = self.simulator.execute(self.reservation, 'checkin')
        self.assertEqual(self.simulator.execute(self.reservation, 'checkin'), result)
        self.assertEqual(self.prepare(), result)
        self.assertEqual(result.attempts, 1)
        self.reservation['guest_name'] = 'Outro Ficticio'
        with self.assertRaises(SimulationBlocked):
            self.simulator.execute(self.reservation, 'checkin')
        with self.assertRaises(SimulationBlocked):
            self.prepare()

    def test_room_change_and_checkout_identity_change_are_blocked(self):
        self.prepare()
        with self.assertRaises(SimulationBlocked):
            self.simulator.execute(dict(self.reservation, room='202'), 'checkin')
        self.simulator.execute(self.reservation, 'checkin')
        for change in (dict(guest_name='Outro Ficticio'), dict(phone='5511999999999'),
                       dict(room='202'), dict(arrival='2030-01-02')):
            with self.subTest(change=tuple(change)):
                with self.assertRaises(SimulationBlocked):
                    self.prepare('checkout', checkout_status='CHECK_OUT_REALIZADO', **change)

    def test_unknown_result_is_not_retryable(self):
        self.prepare()
        result = self.simulator.execute(self.reservation, 'checkin', outcome='uncertain')
        self.assertEqual(result.state, 'SIMULATED_UNCERTAIN')
        for outcome in ('ok', 'error', 'uncertain'):
            with self.assertRaises(SimulationBlocked):
                self.simulator.execute(self.reservation, 'checkin', outcome=outcome)
        self.assertEqual(self.prepare().attempts, 1)

    def test_explicit_failure_can_retry_and_reservations_are_separate(self):
        self.prepare()
        self.assertEqual(self.simulator.execute(self.reservation, 'checkin', outcome='error').state,
                         'SIMULATED_ERROR')
        self.assertEqual(self.simulator.execute(self.reservation, 'checkin').attempts, 2)
        self.assertEqual(self.prepare(external_id='FAKE-002').attempts, 0)
        self.assertEqual(self.prepare(hotel_id='other').attempts, 0)

    def test_unprepared_and_unknown_operations(self):
        with self.assertRaises(SimulationBlocked):
            self.simulator.execute(self.reservation, 'checkin')
        with self.assertRaises(SimulationBlocked):
            self.prepare('send')
        self.prepare()
        with self.assertRaises(SimulationBlocked):
            self.simulator.execute(self.reservation, 'checkin', outcome='sent')
        self.assertEqual(self.prepare().attempts, 0)

    def test_fixture_has_no_io_or_personal_data_in_output(self):
        with patch('socket.socket', side_effect=AssertionError('network forbidden')), \
             patch('sqlite3.connect', side_effect=AssertionError('database forbidden')), \
             patch('builtins.open', side_effect=AssertionError('files forbidden')):
            report = run()
        output = json.dumps(report)
        self.assertTrue(report['uncertain_retry_blocked'])
        self.assertEqual(report['duplicate_attempts'], 1)
        for value in ('52998224725', '5511000000000', 'Hospede Ficticio'):
            self.assertNotIn(value, output)


if __name__ == '__main__':
    unittest.main()
