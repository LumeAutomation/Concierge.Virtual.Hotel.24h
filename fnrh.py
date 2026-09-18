"""In-memory FNRH rehearsal, NOT an official API payload or submission.

Only validates the existing local reservation model; official completeness is
not assessed. No network, credentials, database or persistence is implemented.
"""
from dataclasses import dataclass, replace
import hashlib
import json
from reservations import fields


class SimulationBlocked(ValueError):
    pass


@dataclass(frozen=True)
class Result:
    operation: str
    state: str
    attempts: int = 0


class Simulator:
    """Single-process simulation. Restarting discards idempotency records."""

    def __init__(self):
        self._records = {}
        self._snapshots = {}
        self._identities = {}

    @staticmethod
    def inspect(reservation):
        """Local pending codes only, never personal values."""
        pending = []
        try:
            fields(reservation)
        except (ValueError, TypeError):
            pending.append('INVALID_LOCAL_RESERVATION')
        for name in ('arrival', 'departure'):
            if not reservation.get(name):
                pending.append('MISSING_' + name.upper())
        if reservation.get('pre_status') != 'PRE_CHECKIN_CONCLUIDO':
            pending.append('LOCAL_PRECHECKIN_PENDING')
        return tuple(pending)

    @staticmethod
    def _key(reservation, operation):
        if operation not in ('checkin', 'checkout'):
            raise SimulationBlocked('Operacao desconhecida.')
        identifier = reservation.get('id') or reservation.get('external_id')
        hotel = reservation.get('hotel_id', 'aurora')
        if not isinstance(identifier, str) or not identifier.strip():
            raise SimulationBlocked('Reserva sem identificador local.')
        if not isinstance(hotel, str) or not hotel.strip():
            raise SimulationBlocked('Hotel sem identificador local.')
        return hotel, identifier, operation

    @staticmethod
    def _snapshot(reservation):
        names = ('id', 'hotel_id', 'external_id', 'guest_name', 'cpf', 'phone',
                 'arrival', 'departure', 'room', 'pre_status', 'checkin_status', 'checkout_status')
        content = {name: reservation.get(name) for name in names}
        return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).digest()

    def prepare(self, reservation, operation, *, human_checked=False):
        key = self._key(reservation, operation)
        if human_checked is not True:
            raise SimulationBlocked('Conferencia humana obrigatoria para esta simulacao.')
        if self.inspect(reservation):
            raise SimulationBlocked('Existem pendencias nos dados locais.')
        if reservation.get('checkin_status') != 'CHECK_IN_REALIZADO':
            raise SimulationBlocked('Check-in local ainda nao realizado.')
        identity = self._snapshot(dict(reservation, checkout_status=None))
        if operation == 'checkout':
            checkin = self._records.get((*key[:2], 'checkin'))
            if not checkin or checkin.state != 'SIMULATED_OK':
                raise SimulationBlocked('Simule o check-in com sucesso primeiro.')
            if self._identities[(*key[:2], 'checkin')] != identity:
                raise SimulationBlocked('Dados divergem do check-in simulado; reconciliacao humana necessaria.')
            if reservation.get('checkout_status') != 'CHECK_OUT_REALIZADO':
                raise SimulationBlocked('Check-out local ainda nao realizado.')
        snapshot = self._snapshot(reservation)
        previous = self._records.get(key)
        if previous:
            if self._snapshots[key] != snapshot:
                raise SimulationBlocked('Dados alterados: exige reconciliacao humana.')
            return previous
        self._snapshots[key] = snapshot
        self._identities[key] = identity
        self._records[key] = Result(operation, 'SIMULATED_PREPARED')
        return self._records[key]

    def execute(self, reservation, operation, *, outcome='ok'):
        """Inject a fake outcome. Uncertain results cannot be retried here."""
        key = self._key(reservation, operation)
        previous = self._records.get(key)
        if previous is None:
            raise SimulationBlocked('Prepare e confira a simulacao primeiro.')
        if self._snapshots[key] != self._snapshot(reservation):
            raise SimulationBlocked('Dados alterados desde a conferencia humana.')
        if previous.state == 'SIMULATED_UNCERTAIN':
            raise SimulationBlocked('Resultado incerto: retry bloqueado; reconciliacao humana necessaria.')
        if previous.state == 'SIMULATED_OK':
            return previous
        outcomes = {'ok': 'SIMULATED_OK', 'error': 'SIMULATED_ERROR',
                    'uncertain': 'SIMULATED_UNCERTAIN'}
        if outcome not in outcomes:
            raise SimulationBlocked('Resultado ficticio desconhecido.')
        current = replace(previous, state=outcomes[outcome], attempts=previous.attempts + 1)
        self._records[key] = current
        return current
