"""Bounded official catalogue discovery. Counts/filter echoes are coverage evidence.

These are public website form endpoints, not a promised stable vendor API.
Unexpected markup, repeated pages, ignored filters, or invalid documents fail closed.
"""
from __future__ import annotations

import hashlib
import http.cookiejar
import re
import ssl
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlparse, parse_qs

from deployment.events.clock import IST, now_ist
from deployment.events.models import MacroEvent
from deployment.events.normalization import normalize_event
from deployment.events.sources.base import SourceError

MAX_PAGES = 40
MAX_DOCUMENTS = 5000


def clean(text):
    return ' '.join(text.split())


def listing_date(text):
    for fmt in ('%b %d, %Y', '%d %b %Y', '%B %d, %Y'):
        try:
            return datetime.strptime(clean(text), fmt).date().isoformat()
        except ValueError:
            pass
    raise SourceError('Invalid official listing date')


class Page(HTMLParser):
    """Read forms, simple table rows and PIB release items without executing JS."""
    def __init__(self, data):
        super().__init__(convert_charrefs=True)
        self.fields, self.controls, self.rows, self.items, self.links = {}, {}, [], [], []
        self.select = self.option = self.row = self.cell = self.anchor = None
        self.li = []
        self.text = []
        self.hidden_text_depth = 0
        self.feed(data.decode('utf-8-sig', errors='strict') if isinstance(data, bytes) else data)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('script','style'):
            self.hidden_text_depth += 1
        elif tag == 'input' and a.get('name'):
            self.controls[a.get('id', a['name'])] = a
            if a.get('type') == 'hidden':
                self.fields[a['name']] = a.get('value', '')
        elif tag == 'select':
            self.select = a.get('name')
        elif tag == 'option' and self.select:
            self.option = (a.get('value', ''), 'selected' in a)
        elif tag == 'tr':
            self.row = {'cells':[], 'links':[]}
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = []
        elif tag == 'li':
            if self.li:
                self.li[-1]['has_nested_li'] = True
            self.li.append({'text':[], 'links':[], 'has_nested_li':False})
        elif tag == 'a':
            self.anchor = {'url':a.get('href', ''), 'text':[]}

    def handle_data(self, data):
        if self.hidden_text_depth:
            return
        self.text.append(data)
        if self.cell is not None:
            self.cell.append(data)
        if self.anchor is not None:
            self.anchor['text'].append(data)
        for entry in self.li:
            entry['text'].append(data)

    def handle_endtag(self, tag):
        if tag in ('script','style'):
            self.hidden_text_depth = max(0,self.hidden_text_depth-1)
        elif tag == 'option' and self.option:
            if self.option[1]:
                self.fields[self.select] = self.option[0]
            self.option = None
        elif tag == 'select':
            self.select = None
        elif tag in ('td', 'th') and self.row is not None and self.cell is not None:
            self.row['cells'].append(clean(' '.join(self.cell)))
            self.cell = None
        elif tag == 'a' and self.anchor is not None:
            link = {'url':self.anchor['url'], 'title':clean(' '.join(self.anchor['text']))}
            self.links.append(link)
            if self.row is not None:
                self.row['links'].append(link)
            for entry in self.li:
                entry['links'].append(link)
            self.anchor = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None
            self.cell = None
        elif tag == 'li' and self.li:
            entry = self.li.pop()
            entry['text'] = clean(' '.join(entry['text']))
            if not entry['has_nested_li']:
                self.items.append(entry)


class OfficialSession:
    def __init__(self, host):
        self.host = host
        class Redirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(inner, req, fp, code, msg, headers, target):
                u = urlparse(target)
                if u.scheme != 'https' or u.hostname != host:
                    raise SourceError('Unexpected official catalogue redirect')
                return super().redirect_request(req, fp, code, msg, headers, target)
        self.opener = urllib.request.build_opener(
            Redirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, url, data=None, referer=None):
        u = urlparse(url)
        if u.scheme != 'https' or u.hostname != self.host or u.username or u.password:
            raise SourceError('Non-official catalogue request rejected')
        headers = {'User-Agent':'Mozilla/5.0 SectorRotationEvents/1.0', 'Accept':'text/html'}
        if data is not None:
            headers.update({'Content-Type':'application/x-www-form-urlencoded',
                            'Referer':referer or url, 'Origin':'https://'+self.host})
        body = urlencode(data).encode() if data is not None else None
        for attempt in range(3):
            try:
                with self.opener.open(urllib.request.Request(url, data=body, headers=headers), timeout=25) as response:
                    content = response.read(5_000_001)
                    if not content or len(content) > 5_000_000:
                        raise SourceError('Empty or oversized official catalogue response')
                    return content
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = exc
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise SourceError('Official catalogue request failed after bounded retries') from last


def months(start, end):
    current = date.fromisoformat(start).replace(day=1)
    finish = date.fromisoformat(end).replace(day=1)
    if date.fromisoformat(start) > date.fromisoformat(end) or (date.fromisoformat(end)-date.fromisoformat(start)).days > 90:
        raise SourceError('Official archive window must be ordered and bounded to 90 days')
    while current <= finish:
        yield current
        current = date(current.year+1, 1, 1) if current.month == 12 else date(current.year, current.month+1, 1)


def receipt(source, start, end, scope):
    return {'schema_version':1, 'source':source, 'requested_window':{'start':start,'end':end},
            'scope':scope, 'complete':False, 'pagination_complete':False,
            'pages':[], 'documents':[], 'document_ids':[], 'rejected_items':[],
            'catalogue_duplicates':0, 'accepted_events':0}


def add_page(evidence, url, data, count, **kwargs):
    evidence['pages'].append({'url':url, 'response_sha256':hashlib.sha256(data).hexdigest(),
                              'returned_records':count, 'retrieved_at':now_ist().isoformat(), **kwargs})
    if len(evidence['pages']) > MAX_PAGES:
        raise SourceError('Official catalogue page bound exceeded')


def official_link(url, base, host):
    absolute = urljoin(base, url)
    u = urlparse(absolute)
    if u.scheme != 'https' or u.hostname != host or u.username or u.password:
        raise SourceError('Invalid official document link')
    return absolute


def rbi_catalogue(session, start, end, evidence):
    url = 'https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx'
    records = []
    for month in months(start, end):
        form = Page(session.request(url))
        if 'hdnMonth' not in form.controls or 'hdnYear' not in form.controls or 'btn' not in form.controls:
            raise SourceError('RBI month navigation unavailable or error page')
        fields = dict(form.fields)
        fields.update({form.controls['hdnYear']['name']:str(month.year),
                       form.controls['hdnMonth']['name']:str(month.month),
                       form.controls['btn']['name']:form.controls['btn'].get('value','')})
        data = session.request(url, fields)
        page = Page(data)
        if page.fields.get('hdnYear') != str(month.year) or page.fields.get('hdnMonth') != str(month.month):
            raise SourceError('RBI archive ignored the selected month')
        current = None
        rows = []
        for row in page.rows:
            links = [link for link in row['links'] if re.search(r'(?i)[?&]prid=\d+', link['url'])]
            if not links:
                if row['cells'] and re.fullmatch(r'[A-Za-z]{3} \d{1,2}, \d{4}', row['cells'][0]):
                    current = listing_date(row['cells'][0])
                continue
            if len(links) != 1 or current is None or not current.startswith(month.strftime('%Y-%m')):
                raise SourceError('RBI archive has unscoped or undated document rows')
            link = links[0]
            absolute = official_link(link['url'], url, 'www.rbi.org.in')
            document_id = re.search(r'(?i)[?&]prid=(\d+)', absolute).group(1)
            rows.append({'id':document_id, 'date':current, 'title':link['title'], 'url':absolute})
        all_ids = [re.search(r'(?i)[?&]prid=(\d+)', l['url']).group(1) for l in page.links if re.search(r'(?i)[?&]prid=\d+', l['url'])]
        evidence['catalogue_duplicates'] += len(all_ids)-len(set(all_ids))
        if not rows or len(rows) != len(all_ids) or len(set(all_ids)) != len(all_ids):
            raise SourceError('RBI full-month table is empty, duplicated, or truncated')
        text = clean(' '.join(page.text))
        if (re.search(r'(?i)(next page|load more|page \d+ of \d+)', text)
                or re.search(rb'(?i)\b(?:PageSize|PageIndex|LoadMore|NextPage)\b',data)):
            raise SourceError('RBI archive pagination is unsupported; month is incomplete')
        add_page(evidence, url, data, len(rows), month=month.strftime('%Y-%m'),
                 filters_verified=True, pagination='single full-month table', document_ids=all_ids)
        records.extend(rows)
    return records


def sebi_catalogue(session, start, end, evidence):
    # Use the same public AJAX endpoint/zero-based page selector as entry.js.
    landing = 'https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&smid=0&ssid=7'
    session.request(landing)
    url = 'https://www.sebi.gov.in/sebiweb/ajax/home/getnewslistinfo.jsp'
    records = []; total = None
    for index in range(MAX_PAGES):
        fields = {'nextValue':str(index or 1), 'next':'s' if index == 0 else 'n', 'doDirect':'-1' if index == 0 else str(index),
                  'search':'', 'fromDate':date.fromisoformat(start).strftime('%d-%m-%Y'),
                  'toDate':date.fromisoformat(end).strftime('%d-%m-%Y'), 'fromYear':'','toYear':'',
                  'deptId':'-1','sid':'1','ssid':'7','smid':'0','ssidhidden':'7','intmid':'-1',
                  'sText':'Legal','ssText':'Circulars','smText':''}
        data = session.request(url, fields, referer=landing)
        page = Page(data)
        ranges = re.findall(r'(\d+)\s+to\s+(\d+)\s+of\s+([\d,]+)\s+records', clean(' '.join(page.text)), re.I)
        if not ranges or len(set(ranges)) != 1:
            raise SourceError('SEBI catalogue has no unambiguous pagination count')
        first, last, declared = [int(x.replace(',','')) for x in ranges[0]]
        if total is None: total = declared
        if declared != total or declared > MAX_DOCUMENTS or first != len(records)+1 or last > total or last < first:
            raise SourceError('SEBI catalogue changed counts or repeated/skipped a page')
        rows = []
        for row in page.rows:
            if not row['cells'] or not row['links']: continue
            if not re.fullmatch(r'[A-Za-z]{3} \d{1,2}, \d{4}', row['cells'][0]): continue
            if len(row['links']) != 1: raise SourceError('Ambiguous SEBI document row')
            dt = listing_date(row['cells'][0]);link = row['links'][0]
            absolute = official_link(link['url'], landing, 'www.sebi.gov.in')
            match = re.search(r'_(\d+)\.html$', urlparse(absolute).path)
            if not match or not start <= dt <= end: raise SourceError('SEBI date filter ignored or document ID invalid')
            rows.append({'id':match.group(1), 'date':dt,'title':link['title'],'url':absolute})
        if len(rows) != last-first+1: raise SourceError('SEBI page rows do not match its declared range')
        records.extend(rows)
        if len({r['id'] for r in records}) != len(records):
            evidence['catalogue_duplicates'] += len(records)-len({r['id'] for r in records})
            raise SourceError('SEBI catalogue repeated document IDs')
        add_page(evidence,url,data,len(rows),first=first,last=last,total=total,filters_verified=True,
                 from_date=start,to_date=end,document_ids=[r['id'] for r in rows])
        if last == total: return records
    raise SourceError('SEBI pagination bound reached before completion')


def pib_catalogue(session, start, end, evidence):
    url = 'https://www.pib.gov.in/allRel.aspx?reg=3&lang=1'
    records = []
    for month in months(start,end):
        form = Page(session.request(url))
        prefix = 'ctl00$ContentPlaceHolder1$'
        required = ['__VIEWSTATE','__EVENTVALIDATION',prefix+'ddlYear',prefix+'ddlMonth',prefix+'ddlday',prefix+'ddlMinistry']
        if any(key not in form.fields for key in required): raise SourceError('PIB date-filter form unavailable')
        fields = dict(form.fields)
        fields.update({'__EVENTTARGET':prefix+'ddlday','__EVENTARGUMENT':'',prefix+'ddlday':'0',
                       prefix+'ddlMonth':str(month.month),prefix+'ddlYear':str(month.year),prefix+'ddlMinistry':'0'})
        data = session.request(url, fields)
        page = Page(data)
        for key,value in [(prefix+'ddlday','0'),(prefix+'ddlMonth',str(month.month)),(prefix+'ddlYear',str(month.year)),(prefix+'ddlMinistry','0')]:
            if page.fields.get(key) != value: raise SourceError('PIB ignored date/ministry filters')
        if page.fields.get('ctl00$Bar1$ddlLang') != '1' or page.fields.get('ctl00$Bar1$ddlregion') != '3':
            raise SourceError('PIB English/Delhi scope is not confirmed')
        counts = re.findall(r'Displaying\s+([\d,]+)\s+Press Releases', clean(' '.join(page.text)), re.I)
        if len(set(counts)) != 1: raise SourceError('PIB listing has no declared release count')
        declared = int(counts[0].replace(',',''))
        if declared > MAX_DOCUMENTS: raise SourceError('PIB catalogue document bound exceeded')
        rows = []
        for entry in page.items:
            links = [l for l in entry['links'] if re.search(r'(?i)[?&]PRID=\d+',l['url'])]
            if len(links) != 1: continue
            stamp = re.search(r'Posted On:\s*(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})',entry['text'],re.I)
            if not stamp: raise SourceError('PIB archive item has no publication date')
            dt = listing_date(stamp.group(1))
            if not dt.startswith(month.strftime('%Y-%m')): raise SourceError('PIB archive date is outside selected month')
            link = links[0];absolute = official_link(link['url'],url,'www.pib.gov.in')
            if len(re.findall(r'[A-Za-z]',link['title'])) < 4:
                raise SourceError('PIB catalogue language/title could not be validated')
            document_id = parse_qs(urlparse(absolute).query).get('PRID',[None])[0]
            if not document_id or not document_id.isdigit(): raise SourceError('Invalid PIB release ID')
            rows.append({'id':document_id,'date':dt,'title':link['title'],'url':absolute})
        evidence['catalogue_duplicates'] += len(rows)-len({r['id'] for r in rows})
        if len(rows) != declared or len({r['id'] for r in rows}) != declared:
            raise SourceError('PIB catalogue count is truncated or contains duplicate release IDs')
        add_page(evidence,url,data,len(rows),month=month.strftime('%Y-%m'),declared_total=declared,
                 filters_verified=True,pagination='all-days complete month view',document_ids=[r['id'] for r in rows])
        records.extend(rows)
    return records


def discover(source, start, end, kind, keywords, category, region='India', session=None):
    host = {'rbi':'www.rbi.org.in','sebi':'www.sebi.gov.in','pib':'www.pib.gov.in'}[kind]
    evidence = receipt(source.name,start,end,{'rbi':'RBI press releases','sebi':'SEBI circulars','pib':'PIB all ministries, English Delhi region'}[kind])
    source.coverage_evidence = evidence
    session = session or OfficialSession(host)
    events = []
    try:
        records = {'rbi':rbi_catalogue,'sebi':sebi_catalogue,'pib':pib_catalogue}[kind](session,start,end,evidence)
        if len(records) > MAX_DOCUMENTS: raise SourceError('Combined catalogue document bound exceeded')
        if len({r['id'] for r in records}) != len(records): raise SourceError('Catalogue repeats document IDs across months')
        evidence['pagination_complete'] = True
        for row in records:
            if not start <= row['date'] <= end: continue
            doc = dict(row);doc['status'] = 'irrelevant'
            evidence['documents'].append(doc);evidence['document_ids'].append(row['id'])
            if not any(key in row['title'].lower() for key in keywords): continue
            try:
                published = row['date']
                if kind == 'pib':
                    document_url = 'https://www.pib.gov.in/PressReleasePage.aspx?'+urlencode({'PRID':row['id'],'lang':'1','reg':'3'})
                    data = session.request(document_url);page = Page(data)
                    visible = clean(' '.join(page.text))
                    if not re.search(r'Release ID:\s*'+re.escape(row['id'])+r'\b',visible,re.I):
                        raise SourceError('PIB document identity was not confirmed')
                    match = re.search(r'Posted On:\s*(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s+(\d{1,2}:\d{2}\s*[AP]M)',clean(' '.join(page.text)),re.I)
                    if not match: raise SourceError('PIB official document lacks publication timestamp')
                    stamp = datetime.strptime(clean(match.group(1)+' '+match.group(2)).upper().replace(' AM','AM').replace(' PM','PM'),'%d %b %Y %I:%M%p').replace(tzinfo=IST)
                    if stamp.date().isoformat() != row['date']: raise SourceError('PIB listing/document publication dates disagree')
                    doc['listing_url'] = row['url'];doc['url'] = document_url
                    doc['published_at'] = stamp.isoformat();doc['document_sha256'] = hashlib.sha256(data).hexdigest()
                    published = stamp
                dt,cat,title,sev,reg,last,_ = normalize_event(row['title'],published,raw_category=category,region=region,source_institution=source.institution)
                events.append(MacroEvent(date=dt,category=cat,title=title,severity=sev,region=reg,
                                         source_id='EVT:'+hashlib.sha256(doc['url'].encode()).hexdigest()[:40],
                                         source_institution=source.institution,raw_source_url=doc['url']))
                doc['status'] = 'accepted'
            except (ValueError,SourceError) as exc:
                doc['status'] = 'rejected'
                evidence['rejected_items'].append({'document_id':row['id'],'reason':str(exc)})
        evidence['accepted_events'] = len(events)
        evidence['complete'] = evidence['pagination_complete'] and not evidence['rejected_items']
    except (SourceError,ValueError,UnicodeError) as exc:
        evidence['error'] = str(exc)
        evidence['rejected_items'].append({'document_id':None,'reason':str(exc)})
        evidence['complete'] = False
    return events


def verified_coverage(evidence, source_name, start, end):
    """A source's booleans alone do not suffice for checkpoint advancement."""
    try:
        window = evidence['requested_window']
        ids = evidence['document_ids']
        pages = evidence['pages']
        return (evidence['schema_version'] == 1 and evidence['source'] == source_name
                and evidence['complete'] is True and evidence['pagination_complete'] is True
                and not evidence['rejected_items'] and window['start'] <= start <= end <= window['end']
                and len(ids) == len(set(ids)) and bool(pages)
                and all(page.get('filters_verified') is True
                        and re.fullmatch(r'[0-9a-f]{64}',page.get('response_sha256','')) for page in pages))
    except (KeyError, TypeError, ValueError):
        return False
