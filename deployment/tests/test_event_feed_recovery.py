"""RSS retention, partial-feed preservation, and sanitized diagnostics regressions."""
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from deployment.events.clock import IST
from deployment.events.daily_collector import DailyEventCollector, main
from deployment.events.diagnostics import redact, sanitize
from deployment.events.sources.base import FeedValidationError, SourceError
from deployment.events.sources.rbi import RBISource
from deployment.events.sources.sebi_nse import SebiNseSource
from deployment.events.sources.mospi_mof import MospiMofSource
from deployment.events.storage import EventStorage
from deployment.tests.test_event_automation import Storage, Source, event, coverage_fixture

@pytest.fixture(autouse=True)
def offline_catalogues(monkeypatch):
    # RSS regression fixtures do not include catalogue pages. Never use the network.
    def unavailable(*args,**kwargs): raise SourceError('No archive fixture supplied')
    monkeypatch.setattr('deployment.events.sources.archive.OfficialSession.request',unavailable)


NOW = datetime(2026, 11, 8, 1, tzinfo=IST)


def rss(*items):
    return ('<rss><channel>'+''.join(items)+'</channel></rss>').encode()


def item(title='CPI inflation release', published='2026-11-06', link='https://pib.gov.in/release'):
    return f'<item><title>{title}</title><pubDate>{published}</pubDate><link>{link}</link></item>'


@pytest.mark.parametrize('adapter,host,title',[
    (RBISource,'www.rbi.org.in','Monetary policy statement'),
    (SebiNseSource,'www.sebi.gov.in','Index derivative margin framework'),
])
def test_rbi_sebi_actual_parser_retention_gap_blocks_checkpoint(adapter,host,title):
    source=adapter();storage=Storage({source.name:'2026-11-05'})
    feed=rss(item(title,link='https://'+host+'/release'))
    with patch.object(source,'_http_get',return_value=feed):
        result=DailyEventCollector(False,storage,[source],lambda:NOW).collect()
    detail=result['source_status'][source.name]
    assert source.oldest_publication=='2026-11-06'  # Existing parser field is used.
    assert detail['oldest_publication']=='2026-11-06'
    assert detail['coverage']['required_boundary']=='2026-11-05'
    assert detail['coverage']['unavailable_window']=={'start':'2026-11-05','end':'2026-11-05'}
    assert detail['recovery_reason']=='rss_retention_gap'
    assert not detail['checkpoint_advanced'] and not storage.seen
    assert result['status']=='FAILED'


@pytest.mark.parametrize('adapter,host,title',[
    (RBISource,'www.rbi.org.in','Monetary policy statement'),
    (SebiNseSource,'www.sebi.gov.in','Index derivative margin framework'),
])
def test_checkpoint_covered_but_optional_older_lookback_is_reported(adapter,host,title):
    source=adapter();storage=Storage({source.name:'2026-11-06'})
    with patch.object(source,'_http_get',return_value=rss(item(title,link='https://'+host+'/release'))):
        result=DailyEventCollector(False,storage,[source],lambda:NOW).collect()
    detail=result['source_status'][source.name]
    assert result['status']=='PARTIAL'
    assert detail['coverage']['checkpoint_boundary_available']
    assert not detail['coverage']['requested_window_available']
    assert detail['previous_checkpoint']=='2026-11-06'
    assert not detail['checkpoint_advanced']  # RSS dates alone are no longer proof.


def test_undated_first_item_does_not_discard_later_valid_pib_event():
    source=MospiMofSource()
    with patch.object(source,'_http_get',return_value=rss(item(published=''),item())):
        with pytest.raises(FeedValidationError) as caught:
            source.fetch_incremental('2026-11-01','2026-11-08')
    assert len(caught.value.events)==1
    assert caught.value.events[0].date=='2026-11-06'
    assert source.oldest_publication=='2026-11-06'
    assert source.feed_diagnostics['rejection_reasons']=={'missing_publication_date':1}
    assert source.feed_diagnostics['rejected_item_details']==[{'item_index':1,'reason':'missing_publication_date'}]


@pytest.mark.parametrize('bad_date,reason',[
    ('','missing_publication_date'),('not a date','malformed_publication_date'),
    ('2026-02-30','malformed_publication_date'),('2099-01-01','publication_date_out_of_bounds'),
])
def test_valid_pib_events_survive_malformed_dates_without_success(bad_date,reason):
    source=MospiMofSource();storage=Storage({source.name:'2026-11-06'})
    with patch.object(source,'_http_get',return_value=rss(item(),item(published=bad_date))):
        result=DailyEventCollector(False,storage,[source],lambda:NOW).collect()
    detail=result['source_status'][source.name]
    assert result['status']=='PARTIAL' and detail['status']=='PARTIAL'
    assert result['new_events_inserted']==1 and len(storage.seen)==1
    assert detail['feed_diagnostics']['rejected_items']==1
    assert detail['feed_diagnostics']['rejection_reasons']=={reason:1}
    assert not detail['checkpoint_advanced']
    assert detail['recovery_reason']=='rejected_feed_items'


def test_all_undated_pib_items_are_failed_not_empty_success():
    source=MospiMofSource();storage=Storage({source.name:'2026-11-06'})
    with patch.object(source,'_http_get',return_value=rss(item(published=''),item(published='bad'))):
        result=DailyEventCollector(False,storage,[source],lambda:NOW).collect()
    detail=result['source_status'][source.name]
    assert result['status']=='FAILED' and detail['status']=='ERROR'
    assert detail['feed_diagnostics']['rejected_items']==2
    assert not storage.seen and not detail['checkpoint_advanced']


def test_rejected_items_counts_include_nonmatching_undated_items():
    source=MospiMofSource()
    with patch.object(source,'_http_get',return_value=rss(item(),item('Unrelated announcement',published=''))):
        with pytest.raises(FeedValidationError): source.fetch_live_pib_rss()
    assert source.feed_diagnostics['accepted_events']==1
    assert source.feed_diagnostics['rejected_items']==1


def test_valid_nonpolicy_dates_contribute_to_feed_bounds():
    source=RBISource()
    feed=rss(item('Treasury bills auction','2026-11-01'),item('Monetary policy statement',link='https://www.rbi.org.in/release'))
    with patch.object(source,'_http_get',return_value=feed): events=source.fetch_live_rss()
    assert len(events)==1
    assert source.oldest_publication=='2026-11-01'
    assert source.newest_publication=='2026-11-06'
    assert source.feed_diagnostics['ignored_items']==1


def test_partial_retry_deduplicates_and_only_clean_run_advances():
    source=MospiMofSource();storage=Storage({source.name:'2026-11-06'})
    collector=DailyEventCollector(False,storage,[source],lambda:NOW)
    with patch.object(source,'_http_get',return_value=rss(item(),item(published=''))): first=collector.collect()
    with patch.object(source,'_http_get',return_value=rss(item())): second=collector.collect()
    assert first['status']=='PARTIAL' and second['status']=='PARTIAL'
    assert second['new_events_inserted']==0 and second['duplicates_rejected']==1
    assert not first['source_status'][source.name]['checkpoint_advanced']
    assert not second['source_status'][source.name]['checkpoint_advanced']


def test_partial_source_checkpoint_is_not_recovered_from_execution_log():
    db=MagicMock()
    db.query.return_value=[{'details':{'source_status':{'PIB':{'status':'PARTIAL','window':{'end':'2026-11-08'}}}}},
                           {'details':{'source_status':{'PIB':{'status':'OK','window':{'end':'2026-11-06'}}}}}]
    older=db.query.return_value[1]['details']['source_status']['PIB']
    older['window']['start']='2026-11-06';older['checkpoint_advanced']=True
    older['coverage_evidence']=coverage_fixture('PIB','2026-11-06','2026-11-06')
    assert EventStorage(db).source_checkpoints()=={'PIB':'2026-11-06'}


def test_feed_metadata_is_reset_after_failed_retry():
    source=RBISource()
    with patch.object(source,'_http_get',return_value=rss(item('Monetary policy',link='https://www.rbi.org.in/release'))): source.fetch_live_rss()
    assert source.oldest_publication
    with patch.object(source,'_http_get',side_effect=RuntimeError('network')):
        with pytest.raises(RuntimeError): source.fetch_live_rss()
    assert source.oldest_publication is None and source.feed_diagnostics['total_items']==0


def test_window_fields_separate_lookback_and_checkpoint_extension():
    source=Source();storage=Storage({'RBI':'2026-10-10'})
    result=DailyEventCollector(storage=storage,sources=[source],clock=lambda:NOW).collect(days_back=7)
    detail=result['source_status']['RBI']
    assert result['requested_lookback_days']==7
    assert detail['requested_window']=={'start':'2026-11-01','end':'2026-11-08'}
    assert detail['effective_window']=={'start':'2026-10-08','end':'2026-11-08'}
    assert detail['checkpoint_extension_days']==24
    assert detail['previous_checkpoint']=='2026-10-10'


@pytest.mark.parametrize('previous',['2026-11-09','bad-date','2018-12-31'])
def test_bad_or_future_checkpoint_fails_before_fetch(previous):
    source=Source();result=DailyEventCollector(storage=Storage({'RBI':previous}),sources=[source],clock=lambda:NOW).collect()
    assert result['status']=='FAILED' and not source.calls
    assert not result['source_status']['RBI']['checkpoint_advanced']


def test_ist_boundary_uses_ist_date_even_when_clock_is_utc():
    now=datetime(2026,11,7,20,30,tzinfo=timezone.utc)
    result=DailyEventCollector(storage=Storage(),sources=[Source()],clock=lambda:now).collect(1)
    assert result['requested_window']=={'start':'2026-11-07','end':'2026-11-08'}
    assert result['started_at'].endswith('+05:30')


def test_90_day_recovery_bound_preserved_with_explicit_start():
    source=Source();result=DailyEventCollector(storage=Storage({'RBI':'2026-08-01'}),sources=[source],clock=lambda:NOW).collect(start_date='2026-11-01')
    detail=result['source_status']['RBI']
    assert detail['recovery_reason']=='bounded_window_exceeded' and not source.calls
    assert detail['checkpoint_extension_days']>90


def test_bootstrap_does_not_silently_claim_unavailable_requested_history():
    source=Source(oldest='2026-11-06')
    result=DailyEventCollector(storage=Storage(),sources=[source],clock=lambda:NOW).collect()
    assert result['status']=='FAILED'
    detail=result['source_status']['RBI']
    assert detail['coverage']['boundary_basis']=='requested_start'
    assert detail['recovery_required'] and not detail['checkpoint_advanced']


@pytest.mark.parametrize('message',[
    'postgresql://owner:p%40ssword@host/database?sslmode=require',
    'https://owner:password@host/path',
    'Authorization: Bearer abc123456',
    'Authorization: Basic abc123456',
    'password=abc123456 token=abc123456 api_key=abc123456',
])
def test_common_secret_forms_are_redacted(message):
    value=redact(message)
    assert 'abc123456' not in value and 'p%40ssword' not in value
    assert 'owner:password@' not in value


def test_actions_full_chained_traceback_is_redacted_without_locals(monkeypatch,capsys):
    monkeypatch.setenv('GITHUB_ACTIONS','true')
    monkeypatch.setenv('NEON_API_KEY','sensitive-neon-key')
    monkeypatch.setenv('EVENT_TEST_DATABASE_URL','postgresql://owner:encoded%40password@host/db')
    try:
        try: raise ValueError('password="sensitive-neon-key"')
        except ValueError as cause:
            local_not_captured='this-local-must-not-appear'
            raise RuntimeError('postgresql://owner:encoded%40password@host/db '+('x'*2100)+' END_OF_FULL_TRACE') from cause
    except RuntimeError as exc:
        result=DailyEventCollector(storage=Storage(),sources=[Source(error=exc)],clock=lambda:NOW).collect()
    output=capsys.readouterr()
    assert 'Traceback' in output.err and 'ValueError' in output.err and 'RuntimeError' in output.err
    assert 'END_OF_FULL_TRACE' in output.err
    serialized=json.dumps(result)+output.err
    for forbidden in ['sensitive-neon-key','encoded%40password','this-local-must-not-appear']:
        assert forbidden not in serialized


def test_encoded_password_is_redacted_separately(monkeypatch):
    monkeypatch.setenv('EVENT_TEST_DATABASE_URL','postgresql://owner:encoded%40password@host/db')
    assert 'encoded@password' not in redact('connection failed encoded@password')


def test_cli_exception_reports_useful_sanitized_message(monkeypatch,capsys):
    monkeypatch.setenv('GITHUB_ACTIONS','true')
    with patch('deployment.events.daily_collector.run_collector',side_effect=RuntimeError('feed refused token=abc123456')):
        assert main([])==1
    output=capsys.readouterr()
    assert 'feed refused' in output.out and 'Traceback' in output.err
    assert 'abc123456' not in output.out+output.err


def test_nested_diagnostics_are_redacted(monkeypatch):
    monkeypatch.setenv('ALERT_SECRET','sensitive-alert-value')
    assert sanitize({'sources':[{'message':'sensitive-alert-value'}]})=={'sources':[{'message':'[REDACTED]'}]}


def test_all_invalid_official_references_fail_even_with_trustworthy_feed_dates():
    source=MospiMofSource();storage=Storage({source.name:'2026-11-06'})
    with patch.object(source,'_http_get',return_value=rss(item(link='https://unofficial.invalid/release'))):
        result=DailyEventCollector(False,storage,[source],lambda:NOW).collect()
    detail=result['source_status'][source.name]
    assert result['status']=='FAILED' and detail['status']=='ERROR'
    assert detail['feed_diagnostics']['valid_items']==0
    assert detail['oldest_publication']=='2026-11-06'
    assert detail['recovery_reason']=='unusable_feed'
    assert not detail['checkpoint_advanced'] and not storage.seen


@pytest.mark.parametrize('message',[
    '{"password": "not-in-environment"}',
    "{'api_key': 'not-in-environment'}",
    '{"access_token":"not-in-environment","reason":"feed refused"}',
    '{"client_secret":"not-in-environment"}',
    r'{"password":"not-in-environment\"escaped"}',
])
def test_quoted_secret_keys_are_redacted_without_environment_registration(message):
    output=redact(message)
    assert 'not-in-environment' not in output and 'escaped' not in output
    assert '[REDACTED]' in output


def test_source_value_error_preserves_context_and_redacts_mapping_in_actions(monkeypatch,capsys):
    monkeypatch.setenv('GITHUB_ACTIONS','true')
    source=Source(error=ValueError('Feed date invalid: {"password":"unregistered-credential"}'))
    result=DailyEventCollector(storage=Storage(),sources=[source],clock=lambda:NOW).collect()
    detail=result['source_status'][source.name]
    stderr=capsys.readouterr().err
    assert detail['error_type']=='ValueError' and 'Feed date invalid' in detail['error']
    assert 'Traceback' in stderr and 'ValueError' in stderr
    assert 'unregistered-credential' not in json.dumps(result)+stderr


def test_fourteen_day_request_and_october_ninth_checkpoint_extension_are_distinct():
    source=Source();result=DailyEventCollector(storage=Storage({'RBI':'2026-10-11'}),sources=[source],clock=lambda:NOW).collect(14)
    detail=result['source_status']['RBI']
    assert result['manual_start_date'] is None
    assert detail['requested_window']=={'start':'2026-10-25','end':'2026-11-08'}
    assert detail['effective_window']=={'start':'2026-10-09','end':'2026-11-08'}
    assert detail['checkpoint_extension_days']==16


def test_manual_october_ninth_start_does_not_claim_checkpoint_extension():
    result=DailyEventCollector(storage=Storage(),sources=[Source()],clock=lambda:NOW).collect(14,start_date='2026-10-09')
    detail=result['source_status']['RBI']
    assert result['manual_start_date']=='2026-10-09' and detail['previous_checkpoint'] is None
    assert detail['requested_window']==detail['effective_window']=={'start':'2026-10-09','end':'2026-11-08'}
    assert detail['checkpoint_extension_days']==0
