"""OPT-IN: appends synthetic events only to a separately confirmed Neon test branch.

No schema changes, deletes, historical backfills, production fallback, or live feeds.
No tests execute against Neon unless explicit test configuration passes the guard.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import uuid

from deployment.events.database import EventDatabase
from deployment.events.models import MacroEvent
from deployment.events.storage import EventStorage
from deployment.events.testing import isolated_test_url


def test_isolated_neon_persistence_and_concurrent_idempotency():
    # Guard runs before constructing any database client. Missing config FAILS,
    # rather than silently skipping a manually requested persistence verification.
    connection = isolated_test_url()
    db = EventDatabase(connection_string=connection)
    before = db.query('SELECT * FROM macro_events ORDER BY event_id')
    assert len(before) >= 230, 'Test branch macro_events must contain at least 230 baseline records'
    snapshot = {int(r['event_id']): json.dumps(r, sort_keys=True, default=str) for r in before}
    logs_before = db.query('SELECT count(*) as count FROM pipeline_execution_logs')
    baseline_log_count = int(logs_before[0]['count'])

    token = uuid.uuid4().hex
    event = MacroEvent(date='2026-11-01', category='Indian policy',
                       title='Event automation isolated persistence fixture ' + token,
                       source_id='EVT:' + hashlib.sha256(token.encode()).hexdigest()[:40],
                       raw_source_url='https://www.rbi.org.in/isolated-fixture/' + token)
    created_event_ids = []
    created_log_ids = []
    try:
        def persist():
            return EventStorage(EventDatabase(connection_string=connection)).persist_events([event], dry_run=False)

        dry = EventStorage(db).persist_events([event], dry_run=True)
        assert dry['unique_to_insert'] == 1
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: persist(), range(2)))
        assert sum(row['inserted_count'] for row in outcomes) == 1
        assert persist()['inserted_count'] == 0

        inserted_rows = db.query('SELECT event_id FROM macro_events WHERE source=$1', [event.source_id])
        assert len(inserted_rows) == 1
        created_event_ids.append(int(inserted_rows[0]['event_id']))

        storage = EventStorage(db)
        log_id = storage.start_run(token, event.date)
        created_log_ids.append(log_id)
        storage.finish_run(log_id, {'run_id': token, 'status': 'SUCCESS', 'source_status': {}, 'new_events_inserted': 1}, 1)
        logged = db.query('SELECT status,details FROM pipeline_execution_logs WHERE log_id=$1', [log_id])
        assert logged[0]['status'] == 'SUCCESS'

        after = db.query('SELECT * FROM macro_events ORDER BY event_id')
        current = {int(r['event_id']): json.dumps(r, sort_keys=True, default=str) for r in after}
        assert all(current.get(key) == value for key, value in snapshot.items())
        assert sum(r['source'] == event.source_id for r in after) == 1
    finally:
        for eid in created_event_ids:
            db.query('DELETE FROM macro_events WHERE event_id=$1', [eid])
        for lid in created_log_ids:
            db.query('DELETE FROM pipeline_execution_logs WHERE log_id=$1', [lid])
        final_events = db.query('SELECT count(*) as count FROM macro_events')
        final_logs = db.query('SELECT count(*) as count FROM pipeline_execution_logs')
        assert int(final_events[0]['count']) == len(before), 'Baseline macro_events count must be preserved after cleanup'
        assert int(final_logs[0]['count']) == baseline_log_count, 'Baseline pipeline_execution_logs count must be preserved after cleanup'
