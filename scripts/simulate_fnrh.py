"""Runs embedded fictitious data only; never loads real reservations."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fnrh import Simulator, SimulationBlocked


def run():
    fixture = dict(external_id='FICTICIO-FNRH-001', guest_name='Hospede Ficticio',
                   cpf='52998224725', phone='5511000000000', arrival='2030-01-01',
                   departure='2030-01-03', pre_status='PRE_CHECKIN_CONCLUIDO',
                   checkin_status='CHECK_IN_REALIZADO', checkout_status='PENDENTE')
    simulator = Simulator()
    report = {'mode': 'SIMULATION_ONLY', 'official_payload': False,
              'official_completeness': 'NOT_ASSESSED',
              'pending': simulator.inspect(dict(fixture, arrival=None))}
    report['prepared'] = simulator.prepare(fixture, 'checkin', human_checked=True).state
    report['checkin'] = simulator.execute(fixture, 'checkin').state
    report['duplicate_attempts'] = simulator.execute(fixture, 'checkin').attempts
    departed = dict(fixture, checkout_status='CHECK_OUT_REALIZADO')
    simulator.prepare(departed, 'checkout', human_checked=True)
    report['checkout'] = simulator.execute(departed, 'checkout').state
    for outcome in ('error', 'uncertain'):
        record = dict(fixture, external_id='FICTICIO-' + outcome)
        simulator.prepare(record, 'checkin', human_checked=True)
        report[outcome] = simulator.execute(record, 'checkin', outcome=outcome).state
        if outcome == 'error':
            report['error_retry'] = simulator.execute(record, 'checkin').state
        else:
            try:
                simulator.execute(record, 'checkin')
            except SimulationBlocked:
                report['uncertain_retry_blocked'] = True
    return report


if __name__ == '__main__':
    if len(sys.argv) != 1:
        raise SystemExit('Somente fixture ficticia embutida; nenhum argumento permitido.')
    print(json.dumps(run(), ensure_ascii=False, indent=2))
