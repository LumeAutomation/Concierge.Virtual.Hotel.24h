"""Durable local rehearsal. This module never submits an official FNRH."""
from datetime import datetime, timezone
from fnrh import Simulator, Result, SimulationBlocked
import reservations

PUBLIC_JOB = ('id', 'operation', 'state', 'attempts', 'created_at', 'updated_at')
OUTCOMES = {'ok': 'SIMULATED_OK', 'error': 'SIMULATED_ERROR', 'uncertain': 'SIMULATED_UNCERTAIN'}


def now():
    return datetime.now(timezone.utc).isoformat()


def init_schema(connection):
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS fnrh_jobs (
          id INTEGER PRIMARY KEY, hotel_id TEXT NOT NULL, reservation_id TEXT NOT NULL,
          operation TEXT NOT NULL CHECK(operation IN ('checkin','checkout')),
          state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
          snapshot BLOB NOT NULL, identity BLOB NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          UNIQUE(hotel_id,reservation_id,operation));
        CREATE TABLE IF NOT EXISTS fnrh_events (
          id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES fnrh_jobs(id),
          action TEXT NOT NULL, state TEXT NOT NULL, actor TEXT NOT NULL,
          reason TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS fnrh_events_job ON fnrh_events(job_id);
        ''')


def rows(db, query, params=()):
    cursor = db.execute(query, params)
    return [dict(zip([c[0] for c in cursor.description], r)) for r in cursor.fetchall()]


def public_job(db, job):
    result = {key: job[key] for key in PUBLIC_JOB}
    result['history'] = rows(db, 'SELECT action,state,actor,created_at FROM fnrh_events WHERE job_id=? ORDER BY id', (job['id'],))
    return result


def snapshot(reservation, operation):
    # Completing the local checkout must not invalidate the checkin receipt.
    return Simulator._snapshot(dict(reservation, checkout_status=None) if operation == 'checkin' else reservation)


def overview(connection):
    with connection() as db:
        db.execute('BEGIN')
        result = []
        for reservation in rows(db, 'SELECT * FROM reservations ORDER BY created_at DESC'):
            item = {key: reservation[key] for key in ('id', 'external_id', 'guest_name', 'status', 'pre_status', 'checkin_status', 'checkout_status')}
            pending = list(Simulator.inspect(reservation))
            if reservation['checkin_status'] != 'CHECK_IN_REALIZADO':
                pending.append('LOCAL_CHECKIN_PENDING')
            jobs = rows(db, 'SELECT * FROM fnrh_jobs WHERE hotel_id=? AND reservation_id=? ORDER BY id', (reservation['hotel_id'], reservation['id']))
            if any(j['state'] == 'SIMULATED_UNCERTAIN' for j in jobs):
                pending.append('RECONCILIATION_REQUIRED')
            if any(j['snapshot'] != snapshot(reservation, j['operation']) for j in jobs):
                pending.append('LOCAL_DATA_CHANGED')
            item.update(pending=pending, jobs=[public_job(db, j) for j in jobs])
            result.append(item)
        return dict(mode='simulation', official_enabled=False, reservations=result)


def change(connection, body, actor):
    if not isinstance(body, dict):
        raise SimulationBlocked('Pedido invalido.')
    if not isinstance(actor, str) or not actor.strip():
        raise SimulationBlocked('Ator obrigatorio.')
    if body.get('human_checked') is not True:
        raise SimulationBlocked('Conferencia humana obrigatoria.')
    operation = body.get('operation')
    action = body.get('action')
    rid = body.get('reservation_id')
    if not isinstance(rid, str) or not rid or operation not in ('checkin', 'checkout') or action not in ('simulate', 'reconcile'):
        raise SimulationBlocked('Reserva, operacao ou acao invalida.')
    reason = ''
    if action == 'simulate' and (not isinstance(body.get('outcome', 'ok'), str) or body.get('outcome', 'ok') not in OUTCOMES):
        raise SimulationBlocked('Resultado ficticio desconhecido.')
    if action == 'reconcile':
        reason = body.get('reason')
        if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 1000:
            raise SimulationBlocked('Informe justificativa entre 3 e 1000 caracteres, sem dados pessoais.')
        if body.get('resolution') not in ('confirmed', 'not_sent'):
            raise SimulationBlocked('Resolucao desconhecida.')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        reservation = reservations.row(db, rid)
        key = Simulator._key(reservation, operation)
        previous = rows(db, 'SELECT * FROM fnrh_jobs WHERE hotel_id=? AND reservation_id=? AND operation=?', key)
        job = previous[0] if previous else None
        stamp = now()
        if action == 'reconcile':
            if not job or type(body.get('job_id')) is not int or job['id'] != body['job_id'] or job['state'] != 'SIMULATED_UNCERTAIN':
                raise SimulationBlocked('Somente resultado incerto pode ser reconciliado; confira o registro.')
            state = 'SIMULATED_OK' if body['resolution'] == 'confirmed' else 'SIMULATED_NOT_SENT'
            db.execute('UPDATE fnrh_jobs SET state=?,updated_at=? WHERE id=?', (state, stamp, job['id']))
        else:
            if job and job['snapshot'] != snapshot(reservation, operation):
                raise SimulationBlocked('Dados alterados desde a conferencia humana; envio bloqueado.')
            if job and job['state'] == 'SIMULATED_UNCERTAIN':
                raise SimulationBlocked('Resultado incerto: reconciliacao humana obrigatoria antes de repetir.')
            if job and job['state'] == 'SIMULATED_OK':
                return dict(mode='simulation', official_enabled=False, job=public_job(db, job))
            simulator = Simulator()
            if operation == 'checkout':
                checkins = rows(db, "SELECT * FROM fnrh_jobs WHERE hotel_id=? AND reservation_id=? AND operation='checkin'", key[:2])
                if checkins:
                    checkin = checkins[0]
                    simulator._records[(*key[:2], 'checkin')] = Result('checkin', checkin['state'], checkin['attempts'])
                    simulator._identities[(*key[:2], 'checkin')] = checkin['identity']
            simulator.prepare(reservation, operation, human_checked=True)
            state = OUTCOMES[body.get('outcome', 'ok')]
            if not job:
                cursor = db.execute('''INSERT INTO fnrh_jobs(hotel_id,reservation_id,operation,state,attempts,snapshot,identity,created_at,updated_at)
                    VALUES(?,?,?,?,1,?,?,?,?)''', (*key, state, snapshot(reservation, operation), Simulator._snapshot(dict(reservation, checkout_status=None)), stamp, stamp))
                job = {'id': cursor.lastrowid}
            else:
                db.execute('UPDATE fnrh_jobs SET state=?,attempts=attempts+1,updated_at=? WHERE id=?', (state, stamp, job['id']))
        db.execute('INSERT INTO fnrh_events(job_id,action,state,actor,reason,created_at) VALUES(?,?,?,?,?,?)',
                   (job['id'], action if action == 'simulate' else 'reconcile_' + body['resolution'], state, actor.strip(), reason.strip(), stamp))
        current = rows(db, 'SELECT * FROM fnrh_jobs WHERE id=?', (job['id'],))[0]
        return dict(mode='simulation', official_enabled=False, job=public_job(db, current))

