"""Isolated FNRH v2 HTTP adapter. Never imported by the application.

Caller owns durable deduplication, authorization, domain validation and human
review. An uncertain outcome MUST be reconciled before another call.
"""
from dataclasses import dataclass
from datetime import date, datetime
import base64
import http.client
import json
import math
import re
import ssl
from uuid import UUID

BASE_URL = 'https://fnrh.turismo.serpro.gov.br/FNRH_API/rest/v2'
MAX_RESPONSE = 1024 * 1024


@dataclass(frozen=True)
class HotelConfig:
    hotel_id: str
    base_url: str = BASE_URL
    timeout: float = 15.0

    def __post_init__(self):
        if not isinstance(self.hotel_id, str) or not self.hotel_id.strip():
            raise ValueError('Hotel identity required.')
        if self.base_url != BASE_URL:
            raise ValueError('Unverified FNRH endpoint.')
        if isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float)) or not math.isfinite(self.timeout) or not 0 < self.timeout <= 60:
            raise ValueError('Timeout must be between zero and 60 seconds.')


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes


@dataclass(frozen=True)
class ConnectorResult:
    state: str
    code: str
    status: int | None = None
    reservation_id: str | None = None
    guest_ids: tuple[str, ...] = ()


def _transport(method, url, headers, body, timeout):
    # http.client does not follow redirects, consult .netrc or retry requests.
    # Endpoint is pinned before this function; TLS verifies the official host.
    if not url.startswith(BASE_URL + '/'):
        raise ValueError('Unverified FNRH endpoint.')
    connection = http.client.HTTPSConnection('fnrh.turismo.serpro.gov.br', timeout=timeout, context=ssl.create_default_context())
    try:
        connection.request(method, url.split('serpro.gov.br', 1)[1], body, headers)
        response = connection.getresponse()
        content = response.read(MAX_RESPONSE + 1)
        if len(content) > MAX_RESPONSE:
            raise ValueError('Response limit exceeded.')
        return HttpResponse(response.status, content)
    finally:
        connection.close()


def _uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value.lower()
    except (ValueError, TypeError, AttributeError):
        return False


def _timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', value):
        raise ValueError('Explicit UTC event timestamp required.')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def _cpf(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{11}', value) or len(set(value)) == 1:
        return False
    for size in (9, 10):
        digit = (sum(int(value[i]) * (size + 1 - i) for i in range(size)) * 10) % 11
        if int(value[size]) != (0 if digit == 10 else digit):
            return False
    return True


class FnrhConnector:
    def __init__(self, config, *, username, token, transport=None):
        if not isinstance(config, HotelConfig):
            raise ValueError('Explicit hotel configuration required.')
        if not all(isinstance(v, str) and v and '\r' not in v and '\n' not in v for v in (username, token)) or ':' in username:
            raise ValueError('Invalid credentials.')
        self.config = config
        self._authorization = 'Basic ' + base64.b64encode((username + ':' + token).encode()).decode()
        self._transport = transport or _transport

    def _request(self, hotel_id, method, path, body, content_type, validator, cpf=None):
        if hotel_id != self.config.hotel_id:
            raise ValueError('Hotel configuration mismatch.')
        headers = {'Authorization': self._authorization, 'Accept': 'application/json', 'Content-Type': content_type}
        if cpf is not None:
            headers['cpf_solicitante'] = cpf
        try:
            response = self._transport(method, self.config.base_url + path, headers, body, self.config.timeout)
            # Only explicit rejection statuses documented by the manual.
            if response.status in (400, 401, 403, 404):
                return ConnectorResult('rejected', 'HTTP_REJECTED', response.status)
            if response.status != 200:
                return ConnectorResult('uncertain', 'HTTP_UNCERTAIN', response.status)
            if len(response.body) > MAX_RESPONSE:
                return ConnectorResult('uncertain', 'RESPONSE_LIMIT', response.status)
            decoded = json.loads(response.body)
            result = validator(decoded)
            if result is not None:
                return result
            return ConnectorResult('uncertain', 'RESPONSE_MISMATCH', response.status)
        except Exception:
            # Never surface remote body, credential-containing exception or PII.
            return ConnectorResult('uncertain', 'TRANSPORT_OR_RESPONSE_ERROR')

    def event(self, hotel_id, operation, guest_id, occurred_at):
        if operation not in ('checkin', 'checkout') or not _uuid(guest_id):
            raise ValueError('Valid event and remote guest UUID required.')
        instant = _timestamp(occurred_at)

        def validate(response):
            data = response.get('dados') if isinstance(response, dict) else None
            if not isinstance(data, dict):
                return None
            if data.get('hospede_id') != guest_id or data.get('situacao_id') != operation.upper() + '_REALIZADO':
                return None
            if _timestamp(data.get('data_hora')) != instant:
                return None
            return ConnectorResult('confirmed', 'EVENT_CONFIRMED', 200, guest_ids=(guest_id,))

        return self._request(hotel_id, 'PATCH', '/hospedes/' + guest_id + '/' + operation, occurred_at.encode(), 'text/plain', validate)

    def register(self, hotel_id, payload, *, cpf_solicitante):
        """Accepts an already reviewed OFFICIAL payload, not a local reservation.

        Validation here is structural, not a full FNRH/domain eligibility check.
        """
        if not _cpf(cpf_solicitante):
            raise ValueError('Valid requesting operator CPF required.')
        if not isinstance(payload, dict):
            raise ValueError('Official payload required.')
        reservation, guests = payload.get('reserva'), payload.get('dados_hospede')
        if not isinstance(reservation, dict) or not isinstance(guests, list) or not guests:
            raise ValueError('Official reservation and guests required.')
        number = reservation.get('numero_reserva')
        if not isinstance(number, str) or not number.strip():
            raise ValueError('Reservation number required.')
        try:
            arrival = date.fromisoformat(reservation['data_entrada'])
            departure = date.fromisoformat(reservation['data_saida'])
            if departure < arrival:
                raise ValueError()
            for key in ('quantidade_hospede_adulto', 'quantidade_hospede_menor'):
                if type(reservation[key]) is not int or reservation[key] < 0:
                    raise ValueError()
            if sum(reservation[k] for k in ('quantidade_hospede_adulto', 'quantidade_hospede_menor')) != len(guests):
                raise ValueError()
            if reservation['origem_reserva_id'] not in ('MEIOHOSPEDAGEM', 'OTA'):
                raise ValueError()
            if reservation['origem_reserva_id'] == 'OTA' and not reservation.get('numero_reserva_ota'):
                raise ValueError()
            for guest in guests:
                if not isinstance(guest, dict) or not isinstance(guest.get('dados_pessoais'), dict) or not isinstance(guest.get('situacao_hospede'), str) or not guest['situacao_hospede']:
                    raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise ValueError('Incomplete official reservation payload.') from None
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()

        def validate(response):
            data = response.get('dados') if isinstance(response, dict) else None
            if not isinstance(data, dict):
                return None
            remote, remote_guests = data.get('reserva'), data.get('dados_hospedes')
            if not isinstance(remote, dict) or not _uuid(remote.get('reserva_id')) or not isinstance(remote_guests, list) or len(remote_guests) != len(guests):
                return None
            for key in ('numero_reserva', 'data_entrada', 'data_saida', 'origem_reserva_id', 'quantidade_hospede_adulto'):
                if remote.get(key) != reservation.get(key):
                    return None
            ids = []
            for item in remote_guests:
                if not isinstance(item, dict) or not _uuid(item.get('hospede_id')) or not isinstance(item.get('hospede'), dict):
                    return None
                inner = item['hospede']
                if inner.get('reserva_id') != remote['reserva_id'] or not _uuid(inner.get('pessoa_id')) or not isinstance(inner.get('situacao_hospede_id'), str) or not inner['situacao_hospede_id']:
                    return None
                ids.append(item['hospede_id'])
            if len(set(ids)) != len(ids):
                return None
            return ConnectorResult('confirmed', 'REGISTRATION_CONFIRMED', 200, remote['reserva_id'], tuple(ids))

        return self._request(hotel_id, 'POST', '/hospedagem/registrar', body, 'application/json', validate, cpf_solicitante)
