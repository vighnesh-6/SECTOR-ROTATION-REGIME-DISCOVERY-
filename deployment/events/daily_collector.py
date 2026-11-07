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

from deployment.events.clock import now_ist, IST
from deployment.events.storage import EventStorage
from deployment.events.sources import RBISource, FedUsSource, MospiMofSource, SebiNseSource
from deployment.events.sources.base import SourceError, FeedValidationError
from deployment.events.diagnostics import exception_details, sanitize
from deployment.events.sources.archive import verified_coverage


def _as_ist(value):
    return value.replace(tzinfo=IST) if value.tzinfo is None else value.astimezone(IST)


class DailyEventCollector:
    def __init__(self, dry_run=True, storage=None, sources=None, clock=now_ist):
        self.dry_run = dry_run
        self.storage = storage if storage is not None else EventStorage()
        self.sources = sources if sources is not None else [RBISource(), MospiMofSource(), FedUsSource(), SebiNseSource()]
        self.clock = clock

    def collect(self, days_back=14, start_date=None):
        if not 1 <= days_back <= 90:
            raise ValueError("Collection lookback must be 1..90 days")
        now = _as_ist(self.clock())
        end = now.date()
        floor = date(2019, 1, 1)
        explicit = date.fromisoformat(start_date) if start_date else None
        if explicit and not max(floor, end-timedelta(days=90)) <= explicit <= end:
            raise ValueError("Recovery start must be within the last 90 days")
        requested_start = explicit or max(floor, end-timedelta(days=days_back))
        requested_window = {'start':requested_start.isoformat(), 'end':end.isoformat()}
        run_id = str(uuid.uuid4())
        summary = {'run_id':run_id, 'status':'FAILED', 'dry_run':self.dry_run,
                   'started_at':now.isoformat(), 'new_events_inserted':0,
                   'requested_lookback_days':days_back, 'manual_start_date':start_date,
                   'requested_window':requested_window,
                   'candidates_found':0, 'duplicates_rejected':0, 'source_status':{}}
        started = time.monotonic()
        log_id = None
        try:
            checkpoints = self.storage.source_checkpoints()
            if not self.dry_run:
                log_id = self.storage.start_run(run_id, end.isoformat())
            for source in self.sources:
                previous = checkpoints.get(source.name)
                result = {'status':'ERROR', 'previous_checkpoint':previous,
                          'requested_lookback_days':days_back, 'requested_window':dict(requested_window),
                          'checkpoint_extension_days':0, 'checkpoint_advanced':False}
                summary['source_status'][source.name] = result
                try:
                    prior = date.fromisoformat(previous) if previous else None
                    if prior and not floor <= prior <= end:
                        raise ValueError('Saved source checkpoint is outside valid IST date bounds')
                    start = min(requested_start, max(floor, prior-timedelta(days=2))) if prior else requested_start
                    window = {'start':start.isoformat(), 'end':end.isoformat()}
                    result.update(window=window, effective_window=dict(window),
                                  checkpoint_extension_days=(requested_start-start).days,
                                  effective_window_calendar_dates=(end-start).days+1)
                    if (end-start).days > 90:
                        result.update(recovery_required=True, recovery_reason='bounded_window_exceeded',
                                      recovery_action='Verify the missing official archive interval; do not move the checkpoint or run historical backfill')
                        raise ValueError('RECOVERY_REQUIRED: checkpoint-driven window exceeds 90-day bound')
                    # Avoid carrying successful metadata across failed retries on a reused adapter.
                    if hasattr(source, 'feed_diagnostics'):
                        source.feed_diagnostics = {}
                    source.coverage_evidence = {}
                    partial_error = None
                    try:
                        events = source.fetch_incremental(start_date=window['start'], end_date=window['end'])
                    except FeedValidationError as exc:
                        partial_error = exc
                        details = exception_details(exc, source.name)
                        result.update(details)
                        result['feed_error'] = dict(details)
                        # The adapter did not reach its date filter when parsing raised.
                        # Retain only valid in-window events carried by the parser.
                        events = [e for e in exc.events if window['start'] <= e.date <= window['end']]
                    except SourceError as exc:
                        partial_error = exc
                        result['feed_error'] = exception_details(exc, source.name)
                        events = []
                    # Official catalogue enumeration is independent of recent RSS.
                    # A complete receipt replaces the RSS candidate set, never merges
                    # undated RSS items into an allegedly complete source.
                    archive = getattr(source, 'recover_official_interval', None)
                    archive_events = []
                    if callable(archive):
                        try:
                            archive_events = archive(window['start'], window['end'])
                        except Exception as exc:
                            result['archive_error'] = exception_details(exc, source.name+' archive')
                    evidence = getattr(source, 'coverage_evidence', {}) or {}
                    verified = verified_coverage(evidence, source.name, window['start'], window['end'])
                    if evidence:
                        result['coverage_evidence'] = evidence
                    if verified:
                        events = archive_events
                        partial_error = None
                        result['feed_resolution'] = 'replaced_by_verified_official_catalogue'
                        result.pop('error', None)
                        result.pop('error_type', None)
                    oldest = getattr(source, 'oldest_publication', None)
                    newest = getattr(source, 'newest_publication', None)
                    diagnostics = getattr(source, 'feed_diagnostics', {}) or {}
                    result.update(oldest_publication=oldest, newest_publication=newest,
                                  feed_diagnostics=dict(diagnostics), events_fetched=len(events))
                    summary['candidates_found'] += len(events)
                    # Keep the previous checkpoint boundary protection. Optional older
                    # lookback is reported independently; it is not proof of RSS history.
                    required = previous or requested_start.isoformat()
                    rss_boundary_available = oldest is not None and oldest <= required
                    covered = verified or rss_boundary_available
                    result['coverage'] = {
                        'required_boundary':required, 'boundary_basis':'previous_checkpoint' if previous else 'requested_start',
                        'oldest_publication':oldest, 'newest_publication':newest,
                        'checkpoint_boundary_available':rss_boundary_available,
                        'verified_complete':verified,
                        'verification_method':'official_catalogue' if verified else 'unverified_rss_bounds',
                        'requested_window_available':verified or (oldest is not None and oldest <= requested_start.isoformat()),
                        'effective_window_available':verified or (oldest is not None and oldest <= start.isoformat()),
                        'evidence':'visible RSS publication bounds; not a complete archive guarantee'}
                    if not covered:
                        gap_end = min(end, date.fromisoformat(oldest)-timedelta(days=1)) if oldest else end
                        result['coverage']['unavailable_window'] = {'start':required,'end':gap_end.isoformat()}
                        result.update(recovery_required=True, recovery_reason='rss_retention_gap' if oldest else 'no_trustworthy_feed_dates',
                                      recovery_action='Obtain validated official archive coverage for unavailable_window; retain previous checkpoint')
                        raise ValueError('RECOVERY_REQUIRED: RSS retention does not reach the required boundary')
                    for event in events:
                        if not window['start'] <= event.date <= window['end'] or not event.raw_source_url:
                            raise ValueError('Invalid incremental event')
                        event.__post_init__()
                    persisted = self.storage.persist_events(events, dry_run=self.dry_run)
                    inserted = persisted.get('inserted_count', 0)
                    result.update(status='OK' if verified else 'PARTIAL', inserted=inserted,
                                  would_insert=persisted.get('unique_to_insert',0),
                                  duplicates_rejected=persisted.get('duplicates_rejected',0),
                                  checkpoint_advanced=not self.dry_run and verified,
                                  recovery_required=not verified,
                                  references=[{'source_id':e.source_id,'date':e.date,'url':e.raw_source_url} for e in events])
                    if not verified:
                        result.update(recovery_reason='rejected_feed_items' if partial_error else 'coverage_evidence_required',
                                      recovery_action='Retry or obtain corrected official items; valid items are retained but the checkpoint is not advanced')
                    if evidence:
                        evidence['existing_event_duplicates'] = persisted.get('duplicates_rejected',0)
                        evidence['would_insert'] = persisted.get('unique_to_insert',0) if self.dry_run else inserted
                    summary['new_events_inserted'] += inserted
                    summary['duplicates_rejected'] += persisted.get('duplicates_rejected',0)
                except Exception as exc:
                    result.update(exception_details(exc, source.name))
                    # Preserve parser diagnostics even when fetching never returned.
                    if getattr(source, 'feed_diagnostics', None):
                        result['feed_diagnostics'] = dict(source.feed_diagnostics)
                    result['recovery_required'] = result.get('recovery_required', False) or isinstance(exc, FeedValidationError)
                    result['checkpoint_advanced'] = False
            statuses = [r['status'] for r in summary['source_status'].values()]
            summary['status'] = 'SUCCESS' if statuses and all(x=='OK' for x in statuses) else ('PARTIAL' if any(x in ('OK','PARTIAL') for x in statuses) else 'FAILED')
        except Exception as exc:
            summary.update(exception_details(exc, 'collector'))
            summary['status'] = 'FAILED'
        finally:
            summary['finished_at'] = _as_ist(self.clock()).isoformat()
            summary['duration_ms'] = int((time.monotonic()-started)*1000)
            summary = sanitize(summary)
            if log_id is not None:
                try:
                    self.storage.finish_run(log_id, summary, summary['duration_ms'])
                except Exception as exc:
                    details = exception_details(exc, 'execution-log-finalization')
                    summary['status'] = 'FAILED'
                    summary['error'] = 'ExecutionLogFinalizeFailed'
                    summary['logging_error'] = details
                    for result in summary['source_status'].values():
                        result['checkpoint_advanced'] = False
        return summary


def check_health(storage=None, clock=now_ist):
    """Read-only source-success freshness, accounting for weekday schedules."""
    storage = storage if storage is not None else EventStorage()
    now = _as_ist(clock())
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
        result = {'status':'FAILED', **exception_details(exc, 'cli')}
    result = sanitize(result)
    output = json.dumps(result, indent=2)
    print(output)
    # Runner-managed output is event-specific; no local output files by default.
    if os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as handle:
            handle.write('### Event automation result\n```json\n'+output+'\n```\n')
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    sys.exit(main())
