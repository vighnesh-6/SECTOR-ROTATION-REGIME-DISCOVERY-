"""Append-only macro events; existing records are never updated or deleted."""
from __future__ import annotations
import json
from deployment.events.database import EventDatabase
from deployment.events.deduplication import EventDeduplicator
from deployment.events.models import MacroEvent
from deployment.events.sources.archive import verified_coverage

# Retain full-title/date checks across category changes and a source URL hash for
# revised titles. SSI makes NOT EXISTS safe across competing event collectors.
INSERT_EVENT = """
INSERT INTO macro_events (date, category, title, actual, forecast, previous, source)
SELECT $1::date, $2::text, $3::text, $4, $5, $6, $7::text
WHERE NOT EXISTS (
 SELECT 1 FROM macro_events e WHERE e.date = $1::date AND (
   regexp_replace(lower(e.title), '[^a-z0-9]', '', 'g') =
   regexp_replace(lower($3), '[^a-z0-9]', '', 'g')
   OR (e.source = $7 AND $7 LIKE 'EVT:%')
   OR (e.category = $2 AND
     ARRAY(SELECT DISTINCT value[1] FROM regexp_matches(e.title, '[0-9]+', 'g') AS matches(value) ORDER BY value[1]) =
     ARRAY(SELECT DISTINCT value[1] FROM regexp_matches($3, '[0-9]+', 'g') AS matches(value) ORDER BY value[1]) AND
     (SELECT count(*)::float FROM (
       SELECT unnest(regexp_split_to_array(lower(e.title), '[^a-z0-9]+')) AS token
       INTERSECT SELECT unnest(regexp_split_to_array(lower($3), '[^a-z0-9]+'))
     ) i WHERE length(token) >= 3 AND token NOT IN ('the','and','for','with','from','that','this','over','into','amid'))
     / greatest(1, (SELECT count(*) FROM (
       SELECT unnest(regexp_split_to_array(lower(e.title), '[^a-z0-9]+')) AS token
       UNION SELECT unnest(regexp_split_to_array(lower($3), '[^a-z0-9]+'))
     ) u WHERE length(token) >= 3 AND token NOT IN ('the','and','for','with','from','that','this','over','into','amid'))) >= 0.50
   )
 )
) RETURNING event_id;
"""

class EventStorage:
    def __init__(self, db_client=None):
        self.db = db_client if db_client is not None else EventDatabase()

    def get_db_status(self):
        rows = self.db.query("SELECT COUNT(*)::int AS total_rows, MIN(date)::text AS min_date, MAX(date)::text AS max_date FROM macro_events")
        return rows[0]

    def load_existing_events(self):
        return [MacroEvent.from_db_row(row) for row in self.db.query(
            "SELECT event_id, date::text AS date, category, title, actual, forecast, previous, source FROM macro_events ORDER BY date,event_id")]

    def source_checkpoints(self):
        rows = self.db.query("""
          SELECT details FROM pipeline_execution_logs
          WHERE trigger_type = 'event_collector' AND status IN ('SUCCESS','PARTIAL')
          ORDER BY log_id DESC
        """)
        checkpoints = {}
        recovery_anchors = {}
        for row in rows:
            details = row['details']
            if isinstance(details, str):
                details = json.loads(details)
            for name, value in (details or {}).get('source_status', {}).items():
                if (value.get('status') == 'OK' and value.get('checkpoint_advanced') is True
                        and verified_coverage(value.get('coverage_evidence',{}),name,
                                              value['window']['start'],value['window']['end'])
                        and name not in checkpoints):
                    checkpoints[name] = value['window']['end']
                elif (value.get('status') == 'OK'
                      and value.get('checkpoint_advanced') is not False
                      and value.get('window',{}).get('end')):
                    # Legacy RSS-only success is not proof, but discarding its
                    # boundary could silently skip an outstanding recovery gap.
                    # Retain the earliest such boundary until verified recovery.
                    boundary = value['window']['end']
                    recovery_anchors[name] = min(recovery_anchors.get(name,boundary),boundary)
        for name, boundary in recovery_anchors.items():
            checkpoints.setdefault(name,boundary)
        return checkpoints

    def start_run(self, run_id, session_date):
        rows = self.db.query("""
          INSERT INTO pipeline_execution_logs (session_date,trigger_type,status,step_reached,details)
          VALUES ($1::date,'event_collector','RUNNING','EVENT_FETCH',$2::jsonb) RETURNING log_id
        """, [session_date, json.dumps({'run_id':run_id})])
        return int(rows[0]['log_id'])

    def finish_run(self, log_id, summary, duration_ms):
        # Update only the row created for this run; no historical logs are changed.
        self.db.query("""
          UPDATE pipeline_execution_logs SET status=$2,step_reached='EVENT_FINISHED',
            records_processed=$3,duration_ms=$4,details=$5::jsonb,error_message=$6
          WHERE log_id=$1 AND trigger_type='event_collector'
        """, [log_id, summary['status'], summary.get('new_events_inserted',0), duration_ms,
               json.dumps(summary), summary.get('error')])

    def persist_events(self, candidates, dry_run=True):
        # Re-read on every invocation, including recovery after an unknown outcome.
        unique, rejected = EventDeduplicator(self.load_existing_events()).filter_unique(candidates)
        if dry_run:
            return {'dry_run':True,'unique_to_insert':len(unique),'duplicates_rejected':len(rejected),
                    'sample_rows':[event.to_db_row() for event in unique[:5]]}
        if not unique:
            return {'dry_run':False,'inserted_count':0,'duplicates_rejected':len(rejected)}
        queries = []
        for event in unique:
            row = event.to_db_row()
            queries.append({'query':INSERT_EVENT,'params':[row[key] for key in
                ['date','category','title','actual','forecast','previous','source']]})
        results = self.db.transaction(queries)
        inserted = sum(len(result.get('rows', [])) for result in results)
        return {'dry_run':False,'inserted_count':inserted,
                'duplicates_rejected':len(rejected)+len(unique)-inserted}
