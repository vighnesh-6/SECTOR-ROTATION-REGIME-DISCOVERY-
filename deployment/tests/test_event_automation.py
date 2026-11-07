"""Offline production contracts. No network, databases, or filesystem writes."""
import io
import json
import os
import ssl
import urllib.error
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from deployment.events.clock import IST
from deployment.events.daily_collector import DailyEventCollector, check_health, main
from deployment.events.database import EventDatabase, EventDatabaseError
from deployment.events.deduplication import EventDeduplicator
from deployment.events.models import MacroEvent
from deployment.events.normalization import normalize_datetime_to_date
from deployment.events.sources.base import BaseEventSource, SourceError
from deployment.events.sources.rbi import RBISource
from deployment.events.sources.sebi_nse import SebiNseSource
from deployment.events.storage import EventStorage, INSERT_EVENT
from deployment.events.testing import isolated_test_url

NOW = datetime(2026, 11, 7, 23, tzinfo=IST)


def event(title='RBI policy liquidity release', **kwargs):
    return MacroEvent(date='2026-11-06', category='Monetary policy', title=title,
                      raw_source_url='https://www.rbi.org.in/release', **kwargs)


class Source:
    def __init__(self, name='RBI', events=None, error=None, oldest='2026-10-01'):
        self.name, self.events, self.error = name, events or [], error
        self.oldest_publication = oldest
        self.calls = []

    def fetch_incremental(self, start_date, end_date):
        self.calls.append((start_date,end_date))
        if self.error:
            raise self.error
        return self.events

    def recover_official_interval(self, start_date, end_date):
        self.coverage_evidence = coverage_fixture(self.name,start_date,end_date)
        if self.oldest_publication is None or self.oldest_publication > start_date:
            self.coverage_evidence['complete'] = False
        return self.events


def coverage_fixture(name,start,end):
    return {'schema_version':1,'source':name,'requested_window':{'start':start,'end':end},
            'complete':True,'pagination_complete':True,'rejected_items':[],
            'document_ids':[],'pages':[{'filters_verified':True,'response_sha256':'a'*64}]}


class Storage:
    def __init__(self, checkpoints=None):
        self.checkpoints = checkpoints or {}
        self.created = []
        self.finished = []
        self.seen = set()

    def source_checkpoints(self): return self.checkpoints
    def start_run(self, *args):
        self.created.append(args)
        return 55
    def finish_run(self, *args): self.finished.append(args)
    def persist_events(self, events, dry_run=True):
        new = [e for e in events if e.fingerprint() not in self.seen]
        if not dry_run:
            self.seen.update(e.fingerprint() for e in new)
        return {'inserted_count':0 if dry_run else len(new), 'unique_to_insert':len(new),
                'duplicates_rejected':len(events)-len(new)}


@pytest.mark.parametrize('raw,expected', [
    ('2026-11-06T23:00:00Z','2026-11-07'),
    ('Fri, 06 Nov 2026 20:00:00 -0500','2026-11-07'),
    ('2026-11-06','2026-11-06'),
    ('06 Nov, 2026 +0530','2026-11-06'),
    (datetime(2026,11,6,23),'2026-11-06'),
])
def test_ist_dates(raw,expected):
    assert normalize_datetime_to_date(raw) == expected


@pytest.mark.parametrize('value',['2026-02-30','2026-13-01','garbage'])
def test_invalid_dates(value):
    with pytest.raises(ValueError): normalize_datetime_to_date(value)


def test_model_rejects_invalid_calendar_and_empty_title():
    with pytest.raises(ValueError): MacroEvent(date='2026-02-30',category='x',title='x')
    with pytest.raises(ValueError): event(' ')


@pytest.mark.parametrize('data',[b'',b'<html/>',b'<rss><channel>',b'<rss/>'])
def test_bad_feed_is_failure(data):
    with patch.object(RBISource,'_http_get',return_value=data), pytest.raises(SourceError):
        RBISource().fetch_live_rss()


def test_valid_empty_feed_is_noop():
    with patch.object(RBISource,'_http_get',return_value=b'<rss><channel/></rss>'):
        assert RBISource().fetch_live_rss() == []


@pytest.mark.parametrize('date_value,link', [
    ('','https://www.rbi.org.in/release'),
    ('2026-11-06','http://www.rbi.org.in/release'),
    ('2026-11-06','https://attacker.invalid/release'),
    ('2026-11-06','https://user:password@www.rbi.org.in/release'),
])
def test_relevant_feed_requires_publication_and_official_reference(date_value,link):
    xml=f'<rss><channel><item><title>RBI monetary policy</title><pubDate>{date_value}</pubDate><link>{link}</link></item></channel></rss>'.encode()
    with patch.object(RBISource,'_http_get',return_value=xml),pytest.raises(SourceError):
        RBISource().fetch_live_rss()


def test_incremental_never_uses_static_history():
    src=RBISource()
    with patch.object(src,'fetch_live_rss',return_value=[event()]):
        assert len(src.fetch_incremental('2026-11-01','2026-11-07')) == 1
        assert src.fetch_incremental('2026-11-07','2026-11-07') == []


def test_sebi_live_adapter_filters_enforcement():
    xml=b'<rss><channel><item><title>Index derivative margin framework</title><pubDate>2026-11-06</pubDate><link>https://www.sebi.gov.in/circular</link></item><item><title>Order against individual broker</title><pubDate>2026-11-06</pubDate></item></channel></rss>'
    with patch.object(SebiNseSource,'_http_get',return_value=xml):
        assert len(SebiNseSource().fetch_incremental('2026-11-01','2026-11-07')) == 1


def test_ssl_failure_never_disables_certificate_verification():
    opener=MagicMock()
    opener.open.side_effect=urllib.error.URLError(ssl.SSLCertVerificationError('CERTIFICATE_VERIFY_FAILED'))
    with patch('urllib.request.build_opener',return_value=opener),patch('time.sleep'),patch('ssl._create_unverified_context') as unsafe:
        with pytest.raises(SourceError): BaseEventSource._http_get('https://www.rbi.org.in/feed')
        assert opener.open.call_count == 3
        unsafe.assert_not_called()


def test_plaintext_source_rejected_before_network():
    with pytest.raises(SourceError): BaseEventSource._http_get('http://www.rbi.org.in/feed')


def test_dry_run_does_not_log_or_insert():
    storage=Storage()
    result=DailyEventCollector(storage=storage,sources=[Source(events=[event()])],clock=lambda:NOW).collect()
    assert result['status']=='SUCCESS' and result['new_events_inserted']==0
    assert not storage.created and not storage.finished and not storage.seen
    assert result['source_status']['RBI']['would_insert']==1


def test_live_mode_logs_actual_run_and_idempotent_retry():
    storage=Storage()
    collector=DailyEventCollector(dry_run=False,storage=storage,sources=[Source(events=[event()])],clock=lambda:NOW)
    assert collector.collect()['new_events_inserted']==1
    assert collector.collect()['new_events_inserted']==0
    assert len(storage.created)==len(storage.finished)==2
    assert all(row[0]==55 for row in storage.finished)


def test_partial_failure_preserves_good_source_and_sanitizes_error():
    storage=Storage()
    result=DailyEventCollector(False,storage,[Source('good',[event()]),Source('bad',error=RuntimeError('SECRET'))],lambda:NOW).collect()
    assert result['status']=='PARTIAL' and result['new_events_inserted']==1
    assert result['source_status']['bad']['status']=='ERROR'
    assert 'SECRET' not in json.dumps(result)
    assert storage.finished[0][1]['status']=='PARTIAL'


def test_persistence_failure_does_not_advance_source():
    storage=Storage()
    storage.persist_events=MagicMock(side_effect=RuntimeError('secret'))
    result=DailyEventCollector(False,storage,[Source(events=[event()])],lambda:NOW).collect()
    assert result['status']=='FAILED'
    assert result['source_status']['RBI']['status']=='ERROR'


def test_logging_failure_makes_run_fail():
    storage=Storage()
    storage.finish_run=MagicMock(side_effect=RuntimeError('secret'))
    result=DailyEventCollector(False,storage,[Source()],lambda:NOW).collect()
    assert result['status']=='FAILED' and result['error']=='ExecutionLogFinalizeFailed'


def test_start_logging_failure_prevents_fetch_and_insert():
    storage=Storage();source=Source()
    storage.start_run=MagicMock(side_effect=RuntimeError())
    result=DailyEventCollector(False,storage,[source],lambda:NOW).collect()
    assert result['status']=='FAILED' and source.calls==[]


def test_recovery_expands_past_default_lookback():
    source=Source()
    storage=Storage({'RBI':'2026-10-10'})
    result=DailyEventCollector(storage=storage,sources=[source],clock=lambda:NOW).collect()
    assert result['status']=='SUCCESS'
    assert source.calls[0][0]=='2026-10-08'


def test_rss_retention_gap_requires_recovery_and_does_not_insert():
    storage=Storage({'RBI':'2026-10-10'})
    source=Source(events=[event()],oldest='2026-11-01')
    result=DailyEventCollector(False,storage,[source],lambda:NOW).collect()
    assert result['status']=='FAILED'
    assert result['source_status']['RBI']['recovery_required']
    assert not storage.seen


@pytest.mark.parametrize('days',[0,-1,91])
def test_unbounded_recovery_rejected(days):
    with pytest.raises(ValueError): DailyEventCollector(storage=Storage()).collect(days)


def test_source_checkpoints_use_only_successful_sources():
    db=MagicMock()
    db.query.return_value=[{'details':{'source_status':{'RBI':{'status':'ERROR'},'Fed':{'status':'OK','window':{'end':'2026-11-06'}}}}},
                           {'details':json.dumps({'source_status':{'RBI':{'status':'OK','window':{'end':'2026-11-05'}}}})}]
    for row in db.query.return_value:
        details=row['details']
        if isinstance(details,str): details=json.loads(details);row['details']=details
        for name,value in details['source_status'].items():
            if value['status']=='OK':
                value['window']['start']=value['window']['end']
                value['checkpoint_advanced']=True
                value['coverage_evidence']=coverage_fixture(name,value['window']['start'],value['window']['end'])
    assert EventStorage(db).source_checkpoints()=={'Fed':'2026-11-06','RBI':'2026-11-05'}


def test_log_insert_uses_returned_identity_not_rowcount():
    db=MagicMock();db.query.return_value=[{'log_id':804}]
    assert EventStorage(db).start_run('run','2026-11-06')==804


def test_storage_inserts_only_and_rechecks_in_database():
    db=MagicMock();db.query.return_value=[]
    db.transaction.return_value=[{'rows':[{'event_id':231}]}]
    result=EventStorage(db).persist_events([event()],dry_run=False)
    assert result['inserted_count']==1
    query=db.transaction.call_args.args[0][0]['query'].upper()
    assert 'WHERE NOT EXISTS' in query and 'INSERT INTO MACRO_EVENTS' in query
    assert 'UPDATE' not in query and 'DELETE' not in query and 'CREATE' not in query


def test_same_day_distinct_numbers_not_fuzzy_duplicates():
    assert not EventDeduplicator([event('CPI inflation May 2026 at 4 percent')]).is_duplicate(event('CPI inflation June 2026 at 5 percent'))[0]


def test_fingerprint_does_not_truncate_titles():
    prefix='Identical first forty characters in this title '
    assert event(prefix+'one').fingerprint()!=event(prefix+'two').fingerprint()


def test_same_official_url_hash_deduplicates_revised_title():
    assert EventDeduplicator([event('Original statement',source_id='EVT:same')]).is_duplicate(event('Revised statement',source_id='EVT:same'))[0]


def response(payload):
    mock=MagicMock();mock.__enter__.return_value=io.BytesIO(json.dumps(payload).encode())
    return mock


def test_serializable_transport_retries_whole_batch_on_conflict():
    db=EventDatabase.__new__(EventDatabase)
    db.endpoint='https://example.neon.tech/sql';db.connection_string='not-a-real-secret'
    conflict=urllib.error.HTTPError(db.endpoint,400,'conflict',{},io.BytesIO(b'{"code":"40001"}'))
    queries=[{'query':INSERT_EVENT,'params':['a']}]
    with patch('urllib.request.urlopen',side_effect=[conflict,response({'results':[{'rows':[]}]})]) as call,patch('time.sleep'):
        assert db.transaction(queries)==[{'rows':[]}]
        assert call.call_count==2
        request=call.call_args.args[0]
        assert request.get_header('Neon-batch-isolation-level')=='Serializable'
        assert json.loads(request.data)['queries']==queries


def test_transport_retries_unknown_commit_outcome_through_conditional_insert():
    db=EventDatabase.__new__(EventDatabase);db.endpoint='https://example.neon.tech/sql';db.connection_string='secret'
    with patch('urllib.request.urlopen',side_effect=[TimeoutError(),response({'results':[{'rows':[]}]})]),patch('time.sleep'):
        assert db.transaction([{'query':INSERT_EVENT,'params':[]}])==[{'rows':[]}]


def test_transport_error_does_not_expose_body_or_connection():
    db=EventDatabase.__new__(EventDatabase);db.endpoint='https://example.neon.tech/sql';db.connection_string='secret'
    error=urllib.error.HTTPError(db.endpoint,400,'bad',{},io.BytesIO(b'{"code":"42601","message":"secret"}'))
    with patch('urllib.request.urlopen',side_effect=error),pytest.raises(EventDatabaseError) as caught:
        db.transaction([])
    assert 'secret' not in str(caught.value)


@pytest.mark.parametrize('value',['','postgresql://u:p@ep-calm-rain-a1emw9d9-pooler.ap-southeast-1.aws.neon.tech/neondb'])
def test_isolation_guard_rejects_missing_or_production_target(value,monkeypatch):
    monkeypatch.setenv('EVENT_TEST_DATABASE_URL',value)
    monkeypatch.setenv('EVENT_TEST_BRANCH_CONFIRMED','true')
    with pytest.raises(ValueError): isolated_test_url()


def test_isolation_guard_requires_explicit_confirmation(monkeypatch):
    monkeypatch.setenv('EVENT_TEST_DATABASE_URL','postgresql://u:p@ep-test.ap-southeast-1.aws.neon.tech/neondb')
    monkeypatch.delenv('EVENT_TEST_BRANCH_CONFIRMED',raising=False)
    with pytest.raises(ValueError): isolated_test_url()


@pytest.mark.parametrize('status,exit_code',[('SUCCESS',0),('PARTIAL',1),('FAILED',1)])
def test_cli_failure_exit_codes(status,exit_code,capsys):
    with patch('deployment.events.daily_collector.run_collector',return_value={'status':status}):
        assert main([])==exit_code
    assert status in capsys.readouterr().out


def test_health_accounts_for_weekend_and_stale_sources():
    storage=Storage({s.name:'2026-11-06' for s in [RBISource()]})
    result=check_health(storage,lambda:NOW)
    assert result['expected_session']=='2026-11-06'
    assert result['status']=='FAILED'


def test_workflow_contract():
    workflow=yaml.safe_load(Path('.github/workflows/daily_events.yml').read_text())
    assert workflow['on']['schedule'][0]['cron']=='30 15 * * 1-5'
    assert workflow['on']['workflow_dispatch']['inputs']['mode']['default']=='dry-run'
    assert workflow['permissions']=={'contents':'read'}
    assert workflow['concurrency']['cancel-in-progress'] is False
    assert workflow['jobs']['offline-tests']['strategy']['matrix']['python']==['3.11','3.13']
    script=workflow['jobs']['events']['steps'][2]['run']
    assert 'EVENT_AUTOMATION_ENABLED' in script and 'test-live' in script
    assert 'backfill' not in script and 'run_daily_eod' not in script


def test_230_existing_events_are_not_reinserted_or_modified():
    rows=[{'event_id':i,'date':'2026-11-06','category':'Indian policy',
           'title':f'Existing release identifier {i}', 'actual':'Severity: medium',
           'forecast':'Region: India','previous':'End: 2026-11-06','source':f'ID: E{i:03}'}
          for i in range(1,231)]
    original=json.dumps(rows,sort_keys=True)
    db=MagicMock();db.query.return_value=rows
    candidates=[MacroEvent.from_db_row(row) for row in rows]
    result=EventStorage(db).persist_events(candidates,dry_run=False)
    assert result['inserted_count']==0 and result['duplicates_rejected']==230
    db.transaction.assert_not_called()
    assert json.dumps(rows,sort_keys=True)==original


def test_database_concurrent_rejection_is_counted_as_duplicate():
    db=MagicMock();db.query.return_value=[]
    db.transaction.return_value=[{'rows':[]}]
    result=EventStorage(db).persist_events([event()],dry_run=False)
    assert result['inserted_count']==0 and result['duplicates_rejected']==1


def test_out_of_window_event_is_not_persisted():
    storage=Storage()
    source=Source(events=[MacroEvent(date='2020-01-01',category='Indian policy',title='Old event',raw_source_url='https://www.rbi.org.in/old')])
    result=DailyEventCollector(False,storage,[source],lambda:NOW).collect()
    assert result['status']=='FAILED' and not storage.seen


def test_manual_recovery_cannot_skip_previous_failure_checkpoint():
    source=Source()
    result=DailyEventCollector(storage=Storage({'RBI':'2026-10-10'}),sources=[source],clock=lambda:NOW).collect(start_date='2026-11-01')
    assert result['status']=='SUCCESS' and source.calls[0][0]=='2026-10-08'


def test_recovery_older_than_90_days_stops_before_fetch():
    source=Source()
    result=DailyEventCollector(storage=Storage({'RBI':'2026-01-01'}),sources=[source],clock=lambda:NOW).collect()
    assert result['status']=='FAILED' and source.calls==[]


def test_good_health_requires_every_source():
    from deployment.events.sources import FedUsSource,MospiMofSource
    storage=Storage({s.name:'2026-11-06' for s in [RBISource(),FedUsSource(),MospiMofSource(),SebiNseSource()]})
    assert check_health(storage,lambda:NOW)['status']=='SUCCESS'
