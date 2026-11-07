"""Independent incremental event collection. CLI defaults to a read-only dry run."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

from deployment.events.clock import now_ist
from deployment.events.storage import EventStorage
from deployment.events.sources import RBISource, FedUsSource, MospiMofSource, SebiNseSource
from deployment.events.sources.base import SourceError


class DailyEventCollector:
    def __init__(self, dry_run=True, storage=None, sources=None, clock=now_ist):
        self.dry_run = dry_run
        self.storage = storage if storage is not None else EventStorage()
        self.sources = sources if sources is not None else [RBISource(), MospiMofSource(), FedUsSource(), SebiNseSource()]
        self.clock = clock

    def collect(self, days_back=14, start_date=None):
        if not 1 <= days_back <= 90:
            raise ValueError("Collection lookback must be 1..90 days")
        now = self.clock()
        end = now.date()
        explicit = date.fromisoformat(start_date) if start_date else None
        if explicit and not max(date(2019, 1, 1), end-timedelta(days=90)) <= explicit <= end:
            raise ValueError("Recovery start must be within the last 90 days")
        run_id = str(uuid.uuid4())
        summary = {'run_id':run_id, 'status':'FAILED', 'dry_run':self.dry_run,
                   'started_at':now.isoformat(), 'new_events_inserted':0,
                   'candidates_found':0, 'duplicates_rejected':0, 'source_status':{}}
        started = time.monotonic()
        log_id = None
        try:
            checkpoints = self.storage.source_checkpoints()
            if not self.dry_run:
                log_id = self.storage.start_run(run_id, end.isoformat())
            successful = 0
            for source in self.sources:
                previous = checkpoints.get(source.name)
                start = explicit or end-timedelta(days=days_back)
                if previous:
                    # Never move the cursor backwards, nor drop a failed source's gap.
                    start = min(start, date.fromisoformat(previous)-timedelta(days=2))
                window = {'start':start.isoformat(), 'end':end.isoformat()}
                result = {'status':'ERROR', 'window':window}
                summary['source_status'][source.name] = result
                try:
                    if (end-start).days > 90:
                        raise ValueError("RECOVERY_REQUIRED: gap exceeds 90 days")
                    events = source.fetch_incremental(**{'start_date':window['start'],'end_date':window['end']})
                    oldest = getattr(source, 'oldest_publication', None)
                    # RSS is not an archive. Fail visibly rather than advancing across
                    # an outage that extends beyond the feed's available history.
                    required = previous or (explicit.isoformat() if explicit else None)
                    if required and (oldest is None or oldest > required):
                        raise ValueError("RECOVERY_REQUIRED: feed no longer covers checkpoint")
                    for event in events:
                        if not window['start'] <= event.date <= window['end'] or not event.raw_source_url:
                            raise ValueError("Invalid incremental event")
                        event.__post_init__()
                    persisted = self.storage.persist_events(events, dry_run=self.dry_run)
                    inserted = persisted.get('inserted_count', 0)
                    result.update(status='OK', events_fetched=len(events), inserted=inserted,
                                  would_insert=persisted.get('unique_to_insert',0),
                                  duplicates_rejected=persisted.get('duplicates_rejected',0),
                                  oldest_publication=oldest,
                                  references=[{'source_id':e.source_id,'date':e.date,'url':e.raw_source_url} for e in events])
                    summary['candidates_found'] += len(events)
                    summary['new_events_inserted'] += inserted
                    summary['duplicates_rejected'] += persisted.get('duplicates_rejected',0)
                    successful += 1
                except Exception as exc:
                    # Exception text can contain secrets from third-party/shared code.
                    result['error_type'] = type(exc).__name__
                    if isinstance(exc, SourceError):
                        result['error'] = str(exc)  # controlled, sanitized source diagnostics
                    result['recovery_required'] = isinstance(exc, ValueError) and str(exc).startswith('RECOVERY_REQUIRED:')
            summary['status'] = 'SUCCESS' if successful == len(self.sources) and successful else ('PARTIAL' if successful else 'FAILED')
        except Exception as exc:
            summary['status'] = 'FAILED'
            summary['error'] = type(exc).__name__
        finally:
            summary['finished_at'] = self.clock().isoformat()
            summary['duration_ms'] = int((time.monotonic()-started)*1000)
            if log_id is not None:
                try:
                    self.storage.finish_run(log_id, summary, summary['duration_ms'])
                except Exception:
                    summary['status'] = 'FAILED'
                    summary['error'] = 'ExecutionLogFinalizeFailed'
        return summary


def check_health(storage=None, clock=now_ist):
    """Read-only source-success freshness, accounting for weekday schedules."""
    storage = storage if storage is not None else EventStorage()
    now = clock()
    expected = now.date()
    if now.hour < 23:  # two-hour allowance for the 21:00 schedule
        expected -= timedelta(days=1)
    while expected.weekday() >= 5:
        expected -= timedelta(days=1)
    points = storage.source_checkpoints()
    missing = [s.name for s in [RBISource(),MospiMofSource(),FedUsSource(),SebiNseSource()]
               if points.get(s.name, '') < expected.isoformat()]
    return {'status':'FAILED' if missing else 'SUCCESS', 'expected_session':expected.isoformat(), 'stale_sources':missing}


def run_collector(days_back=14, dry_run=True, start_date=None):
    return DailyEventCollector(dry_run=dry_run).collect(days_back, start_date)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=14)
    parser.add_argument('--start-date', help='Bounded recent recovery only; never historical backfill')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--check-health', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = check_health() if args.check_health else run_collector(args.days, not args.live, args.start_date)
    except Exception as exc:
        result = {'status':'FAILED','error':type(exc).__name__}
    output = json.dumps(result, indent=2)
    print(output)
    # Runner-managed output is event-specific; no local output files by default.
    if os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as handle:
            handle.write('### Event automation result\n```json\n'+output+'\n```\n')
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    sys.exit(main())
