import json
import unittest
from unittest.mock import patch, MagicMock

from fnrh_connector import BASE_URL, HotelConfig, FnrhConnector, HttpResponse, _transport

GUEST = '550e8400-e29b-41d4-a716-446655440010'
RESERVATION = '550e8400-e29b-41d4-a716-446655440011'
PERSON = '550e8400-e29b-41d4-a716-446655440012'
INSTANT = '2026-09-18T15:00:00.000Z'


class ConnectorTests(unittest.TestCase):
    def connector(self, body=None, status=200, error=None):
        self.calls = []
        def transport(*args):
            self.calls.append(args)
            if error:
                raise error
            return HttpResponse(status, json.dumps(body).encode())
        return FnrhConnector(HotelConfig('hotel-a'), username='synthetic-user', token='synthetic-secret', transport=transport)

    def event_response(self, operation='checkin'):
        return {'dados': {'hospede_id': GUEST, 'situacao_id': operation.upper() + '_REALIZADO', 'data_hora': INSTANT}}

    def payload(self):
        return {'reserva': {'numero_reserva': 'FAKE-1', 'data_entrada': '2026-09-18', 'data_saida': '2026-09-19', 'origem_reserva_id': 'MEIOHOSPEDAGEM', 'quantidade_hospede_adulto': 1, 'quantidade_hospede_menor': 0}, 'dados_hospede': [{'dados_pessoais': {'nome': 'Pessoa Ficticia'}, 'situacao_hospede': 'PRECHECKIN_PENDENTE'}]}

    def registration_response(self):
        reservation = dict(self.payload()['reserva'], reserva_id=RESERVATION)
        return {'dados': {'reserva': reservation, 'dados_hospedes': [{'hospede_id': GUEST, 'hospede': {'reserva_id': RESERVATION, 'pessoa_id': PERSON, 'situacao_hospede_id': 'PRECHECKIN_PENDENTE'}}]}}

    def test_confirmed_events_require_matching_id_state_and_time(self):
        for operation in ('checkin', 'checkout'):
            connector = self.connector(self.event_response(operation))
            result = connector.event('hotel-a', operation, GUEST, INSTANT)
            self.assertEqual(result.state, 'confirmed')
            method, url, headers, body, timeout = self.calls[0]
            self.assertEqual(method, 'PATCH')
            self.assertEqual(url, BASE_URL + '/hospedes/' + GUEST + '/' + operation)
            self.assertEqual(body, INSTANT.encode())
            self.assertEqual(headers['Content-Type'], 'text/plain')
            self.assertTrue(headers['Authorization'].startswith('Basic '))
            self.assertEqual(timeout, 15)

    def test_mismatched_success_is_uncertain(self):
        for field, value in [('hospede_id', RESERVATION), ('situacao_id', 'PRECHECKIN_PENDENTE'), ('data_hora', '2026-09-19T15:00:00Z')]:
            response = self.event_response()
            response['dados'][field] = value
            connector = self.connector(response)
            self.assertEqual(connector.event('hotel-a', 'checkin', GUEST, INSTANT).state, 'uncertain')

    def test_malformed_success_is_uncertain(self):
        for response in ({}, {'dados': []}, None, {'dados': {'hospede_id': GUEST}}):
            connector = self.connector(response)
            self.assertEqual(connector.event('hotel-a', 'checkin', GUEST, INSTANT).state, 'uncertain')

    def test_status_classification_and_no_retries(self):
        for status in (302, 307, 308, 408, 409, 429, 500, 503, 201, 204):
            connector = self.connector(status=status)
            self.assertEqual(connector.event('hotel-a', 'checkin', GUEST, INSTANT).state, 'uncertain')
            self.assertEqual(len(self.calls), 1)
        for status in (400, 401, 403, 404):
            connector = self.connector(status=status)
            self.assertEqual(connector.event('hotel-a', 'checkin', GUEST, INSTANT).state, 'rejected')

    def test_timeout_never_retries_or_exposes_exception(self):
        connector = self.connector(error=TimeoutError('synthetic-secret CPF'))
        result = connector.event('hotel-a', 'checkin', GUEST, INSTANT)
        self.assertEqual(result.state, 'uncertain')
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn('synthetic-secret', repr(result))
        self.assertNotIn('synthetic-secret', repr(connector))

    def test_hotel_scope_and_invalid_inputs_fail_before_transport(self):
        connector = self.connector()
        for hotel, operation, guest, instant in [('hotel-b', 'checkin', GUEST, INSTANT), ('hotel-a', 'delete', GUEST, INSTANT), ('hotel-a', 'checkin', '../guest', INSTANT), ('hotel-a', 'checkin', GUEST, '2026-09-18T15:00:00')]:
            with self.assertRaises(ValueError):
                connector.event(hotel, operation, guest, instant)
        self.assertFalse(self.calls)

    def test_configuration_pins_exact_https_endpoint(self):
        for url in ('http://fnrh.turismo.serpro.gov.br/FNRH_API/rest/v2', BASE_URL + '/', 'https://evil.test', BASE_URL + '?q=1', 'https://fnrh.turismo.serpro.gov.br.evil.test'):
            with self.assertRaises(ValueError):
                HotelConfig('hotel-a', base_url=url)
        for timeout in (0, -1, 61, float('nan'), True):
            with self.assertRaises(ValueError):
                HotelConfig('hotel-a', timeout=timeout)

    def test_registration_returns_only_remote_ids(self):
        connector = self.connector(self.registration_response())
        result = connector.register('hotel-a', self.payload(), cpf_solicitante='52998224725')
        self.assertEqual(result.state, 'confirmed')
        self.assertEqual(result.reservation_id, RESERVATION)
        self.assertEqual(result.guest_ids, (GUEST,))
        self.assertEqual(self.calls[0][0], 'POST')
        self.assertEqual(self.calls[0][2]['cpf_solicitante'], '52998224725')

    def test_registration_wrong_reservation_or_missing_guests_is_uncertain(self):
        for response in ({'dados': {'reserva': {'reserva_id': RESERVATION}, 'dados_hospedes': []}}, self.registration_response()):
            if response['dados']['dados_hospedes']:
                response['dados']['reserva']['numero_reserva'] = 'OTHER'
            connector = self.connector(response)
            self.assertEqual(connector.register('hotel-a', self.payload(), cpf_solicitante='52998224725').state, 'uncertain')

    def test_local_payload_and_invalid_operator_blocked(self):
        connector = self.connector()
        with self.assertRaises(ValueError):
            connector.register('hotel-a', {'guest_name': 'Fake'}, cpf_solicitante='52998224725')
        with self.assertRaises(ValueError):
            connector.register('hotel-a', self.payload(), cpf_solicitante='11111111111')
        self.assertFalse(self.calls)

    def test_standard_transport_closes_without_following_redirect(self):
        connection = MagicMock()
        connection.getresponse.return_value.status = 307
        connection.getresponse.return_value.read.return_value = b''
        with patch('fnrh_connector.http.client.HTTPSConnection', return_value=connection) as create:
            response = _transport('PATCH', BASE_URL + '/hospedes/' + GUEST + '/checkin', {}, b'', 2)
        self.assertEqual(response.status, 307)
        self.assertEqual(create.call_count, 1)
        self.assertEqual(connection.request.call_count, 1)
        connection.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
