"""Offline official catalogue protocol and checkpoint-proof regressions."""
from datetime import datetime
from unittest.mock import MagicMock, patch
import hashlib

import pytest

from deployment.events.clock import IST
from deployment.events.daily_collector import DailyEventCollector
from deployment.events.sources.archive import (
    Page, discover, verified_coverage, months, OfficialSession, official_link)
from deployment.events.sources.base import SourceError
from deployment.events.sources import RBISource, SebiNseSource, MospiMofSource
from deployment.events.storage import EventStorage
from deployment.tests.test_event_automation import Storage, event, coverage_fixture

START, END = '2026-10-09','2026-11-08'
NOW = datetime(2026,11,8,12,tzinfo=IST)


def rbi_html(month=10, rows=None):
    rows = rows if rows is not None else [('101','Oct 15, 2026','Monetary policy statement')]
    form = f'<input type="hidden" name="hdnYear" id="hdnYear" value="2026"><input type="hidden" name="hdnMonth" id="hdnMonth" value="{month}"><input type="submit" name="UsrFontCntr$btn" id="btn" value="">'
    return (form+'<table>'+''.join(f'<tr><td>{dt}</td></tr><tr><td><a href=BS_PressReleaseDisplay.aspx?prid={id}>{title}</a></td></tr>' for id,dt,title in rows)+'</table>').encode()


def sebi_html(first,last,total,rows):
    return (f'<div>{first} to {last} of {total} records</div><table>'+
            ''.join(f'<tr><td>{dt}</td><td><a href="https://www.sebi.gov.in/legal/circulars/oct-2026/document_{id}.html">{title}</a></td></tr>' for id,dt,title in rows)+'</table>').encode()


def pib_html(month=10,rows=None,declared=None):
    rows = rows if rows is not None else [('301','28 Oct 2026','CPI inflation release')]
    controls = '<input type="hidden" name="__VIEWSTATE" value="public-form"><input type="hidden" name="__EVENTVALIDATION" value="public-token">'
    values={'ctl00$Bar1$ddlLang':'1','ctl00$Bar1$ddlregion':'3',
            'ctl00$ContentPlaceHolder1$ddlYear':'2026','ctl00$ContentPlaceHolder1$ddlMonth':str(month),
            'ctl00$ContentPlaceHolder1$ddlday':'0','ctl00$ContentPlaceHolder1$ddlMinistry':'0'}
    controls += ''.join(f'<select name="{k}"><option selected value="{v}">value</option></select>' for k,v in values.items())
    count = len(rows) if declared is None else declared
    # Nested one-child lists previously inflated parsed counts.
    return (controls+f'<div>Displaying {count} Press Releases</div><ul><li><ul>'+
            ''.join(f'<li><a href="/PressReleaseDetail.aspx?PRID={id}">{title}</a><span>Posted On: {dt}</span></li>' for id,dt,title in rows)+
            '</ul></li></ul>').encode()


class Session:
    def __init__(self,responder):self.responder=responder;self.calls=[]
    def request(self,url,data=None,referer=None):
        self.calls.append((url,data,referer))
        return self.responder(url,data)


def run(kind,responder,start=START,end=END):
    source={'rbi':RBISource,'sebi':SebiNseSource,'pib':MospiMofSource}[kind]()
    session=Session(responder)
    events=discover(source,start,end,kind,['monetary policy','derivative','inflation'],None,session=session)
    return source,events,session


def test_rbi_month_form_and_full_table_prove_range():
    def respond(url,data):
        return rbi_html(month=int(data['hdnMonth']) if data else 0,
                        rows=[('101','Oct 15, 2026','Monetary policy statement')] if not data or data['hdnMonth']=='10' else [('102','Nov 06, 2026','Monetary policy update')])
    source,events,session=run('rbi',respond)
    e=source.coverage_evidence
    assert e['complete'] and e['pagination_complete'] and len(events)==2
    assert e['document_ids']==['101','102']
    assert [call[1]['hdnMonth'] for call in session.calls if call[1]]==['10','11']
    assert verified_coverage(e,source.name,START,END)


def test_rbi_ignored_month_does_not_prove_coverage():
    source,_,_=run('rbi',lambda u,d:rbi_html(11))
    assert not source.coverage_evidence['complete']
    assert 'ignored' in source.coverage_evidence['error']


def test_rbi_error_page_is_not_empty_coverage():
    source,_,_=run('rbi',lambda u,d:b'<html>Error.aspx</html>')
    assert not source.coverage_evidence['complete']
    assert source.coverage_evidence['rejected_items']


def test_rbi_document_outside_echoed_month_rejected():
    source,_,_=run('rbi',lambda u,d:rbi_html(int(d['hdnMonth']) if d else 0,[('1','Sep 30, 2026','Monetary policy')]))
    assert not source.coverage_evidence['complete']


def test_sebi_two_pages_require_contiguous_counts_and_date_filters():
    def respond(url,data):
        if data is None:return b'<html>SEBI</html>'
        assert data['fromDate']=='09-10-2026' and data['toDate']=='08-11-2026'
        if data['next']=='s':return sebi_html(1,2,3,[('11','Nov 05, 2026','Derivative policy'),('12','Oct 30, 2026','Margin')])
        assert data['doDirect']=='1'
        return sebi_html(3,3,3,[('13','Oct 15, 2026','Derivative settlement')])
    source,events,session=run('sebi',respond)
    e=source.coverage_evidence
    assert e['complete'] and len(e['pages'])==2 and e['document_ids']==['11','12','13']
    assert len(events)==2


@pytest.mark.parametrize('second',[
    sebi_html(1,1,2,[('12','Oct 15, 2026','Derivative')]),
    sebi_html(2,2,3,[('12','Oct 15, 2026','Derivative')]),
    sebi_html(2,2,2,[('11','Oct 15, 2026','Derivative')]),
])
def test_sebi_repeated_page_changed_total_or_duplicate_id_blocks(second):
    def respond(url,data):
        if data is None:return b'<html/>'
        return sebi_html(1,1,2,[('11','Nov 05, 2026','Derivative')]) if data['next']=='s' else second
    source,_,_=run('sebi',respond)
    assert not source.coverage_evidence['complete']


def test_sebi_date_filter_ignored_blocks():
    source,_,_=run('sebi',lambda u,d:sebi_html(1,1,1,[('1','Sep 01, 2026','Derivative')]) if d else b'landing')
    assert not source.coverage_evidence['complete']


def test_sebi_malformed_row_count_cannot_advance():
    source,_,_=run('sebi',lambda u,d:sebi_html(1,2,2,[('1','Oct 15, 2026','Derivative')]) if d else b'landing')
    assert not source.coverage_evidence['complete']


def pib_session(document=b'<p>Posted On: 28 OCT 2026 4:00PM by PIB Delhi</p><p>Release ID: 301</p>'):
    def respond(url,data):
        if 'PressReleasePage' in url:return document
        if data is None:return pib_html(0,[])
        if data['ctl00$ContentPlaceHolder1$ddlMonth']=='10':return pib_html()
        return pib_html(11,[])
    return respond


def test_pib_counts_identity_timestamp_and_nested_lists():
    source,events,session=run('pib',pib_session())
    e=source.coverage_evidence
    assert e['complete'] and len(events)==1 and e['document_ids']==['301']
    assert e['documents'][0]['published_at']=='2026-10-28T16:00:00+05:30'
    assert len(e['documents'][0]['document_sha256'])==64
    assert any('PressReleasePage.aspx?PRID=301' in c[0] for c in session.calls)
    assert len(Page(pib_html()).items)==1


@pytest.mark.parametrize('document',[
    b'<p>Release ID: 301</p>',
    b'<p>Posted On: 28 OCT 2026 4:00PM by PIB Delhi</p><p>Release ID: 999</p>',
    b'<p>Posted On: 29 OCT 2026 4:00PM by PIB Delhi</p><p>Release ID: 301</p>',
    b'<script>Posted On: 28 OCT 2026 4:00PM</script><p>Release ID: 301</p>',
])
def test_pib_no_invented_timestamp_or_wrong_document_identity(document):
    source,events,_=run('pib',pib_session(document))
    assert not source.coverage_evidence['complete']
    assert source.coverage_evidence['rejected_items'] and events==[]


def test_pib_truncated_month_blocks():
    source,_,_=run('pib',lambda u,d:pib_html(10,declared=2) if d else pib_html(0,[]))
    assert not source.coverage_evidence['complete']


def test_pib_ignored_filters_block():
    source,_,_=run('pib',lambda u,d:pib_html(11) if d else pib_html(0,[]))
    assert not source.coverage_evidence['complete']


def test_archive_uses_only_official_https_links():
    with pytest.raises(SourceError):official_link('https://attacker.invalid/x','https://www.pib.gov.in','www.pib.gov.in')
    with pytest.raises(SourceError):OfficialSession('www.pib.gov.in').request('http://www.pib.gov.in/x')


@pytest.mark.parametrize('start,end',[('2026-11-08','2026-10-09'),('2025-01-01','2026-11-08')])
def test_archive_window_bounds(start,end):
    with pytest.raises(SourceError):list(months(start,end))


def test_coverage_requires_receipt_not_old_rss_date():
    class RSSOnly:
        name='RSS only';oldest_publication='2026-01-01'
        def fetch_incremental(self,**kwargs):return []
    storage=Storage();result=DailyEventCollector(False,storage,[RSSOnly()],lambda:NOW).collect(start_date=START)
    detail=result['source_status']['RSS only']
    assert detail['status']=='PARTIAL' and not detail['checkpoint_advanced']
    assert detail['recovery_reason']=='coverage_evidence_required'


def test_verified_archive_bridges_rss_gap_and_advances_only_normal_success():
    source=RBISource();source.oldest_publication='2026-11-06'
    def archive(start_date,end_date):
        source.coverage_evidence=coverage_fixture(source.name,start_date,end_date)
        return [event()]
    storage=Storage()
    with patch.object(source,'fetch_incremental',return_value=[]),patch.object(source,'recover_official_interval',side_effect=archive):
        result=DailyEventCollector(False,storage,[source],lambda:NOW).collect(start_date=START)
    detail=result['source_status'][source.name]
    assert result['status']=='SUCCESS' and detail['checkpoint_advanced']
    assert detail['oldest_publication']=='2026-11-06'
    assert not detail['coverage']['checkpoint_boundary_available']
    assert detail['coverage']['verified_complete']
    assert detail['coverage_evidence']['existing_event_duplicates']==0


def test_unverified_historical_ok_log_retains_conservative_recovery_boundary():
    db=MagicMock();db.query.return_value=[{'details':{'source_status':{'RBI':{'status':'OK','checkpoint_advanced':True,'window':{'start':START,'end':END}}}}}]
    assert EventStorage(db).source_checkpoints()=={'RBI':END}
    db.query.return_value.append({'details':{'source_status':{'RBI':{'status':'OK','window':{'end':START}}}}})
    assert EventStorage(db).source_checkpoints()=={'RBI':START}
    source=RBISource()
    with patch.object(source,'fetch_incremental',return_value=[]),patch.object(source,'recover_official_interval',return_value=[]):
        result=DailyEventCollector(False,Storage({source.name:START}),[source],lambda:NOW).collect()
    detail=result['source_status'][source.name]
    assert detail['window']['start']=='2026-10-07'
    assert not detail['checkpoint_advanced'] and detail['status']=='ERROR'


def test_receipt_rejects_missing_hash_wrong_source_and_partial_range():
    e=coverage_fixture('RBI',START,END)
    assert not verified_coverage(e,'Other',START,END)
    assert not verified_coverage(e,'RBI','2026-10-01',END)
    e['pages'][0]['response_sha256']='not-a-hash'
    assert not verified_coverage(e,'RBI',START,END)
