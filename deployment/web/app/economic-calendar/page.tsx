'use client';
import {useState} from 'react';
import { TerminalPanel } from '@/components/ui/terminal-panel';
import { MetricTile } from '@/components/ui/metric-tile';
import { SectionHeader } from '@/components/ui/section-header';
import { DataTable } from '@/components/ui/data-table';
import { StatusBadge } from '@/components/ui/status-badge';
import { EmptyState } from '@/components/ui/empty-state';
import { Refresh } from '@/components/analytics/controls';
import { useApi } from '@/lib/use-api';
export default function EconomicCalendarPage(){
 const [category,setCategory]=useState(''),[offset,setOffset]=useState(0);
 const {data,error,loading,refresh}=useApi<any>('/api/v1/events?limit=50&offset='+offset+(category?'&category='+encodeURIComponent(category):''));
 return <div className="space-y-5">
 <SectionHeader title="Economic event calendar" description="Stored macroeconomic event catalog · database dates and metadata · no inferred release times" action={<Refresh loading={loading} onClick={refresh}/>}/>
 <div className="grid gap-4 md:grid-cols-3"><MetricTile label="Matching catalog records" value={data?.total} subtitle={category||'All categories'}/><MetricTile label="Latest matching event" value={data?.latest_date}/><MetricTile label="Displayed records" value={data?data.count:null} subtitle={data?`Rows ${data.count?offset+1:0}?${offset+data.count}`:'Loading'}/></div>
 <TerminalPanel title="Chronological event records" subtitle="Historical catalog entries are not a schedule of confirmed future releases." headerRight={<label className="text-xs">Category <select className="control max-w-[220px]" value={category} onChange={e=>{setCategory(e.target.value);setOffset(0);}}><option value="">All categories</option>{data?.categories?.map((c:any)=><option key={c.category} value={c.category}>{c.category}</option>)}</select></label>}>
 {error?<EmptyState title="Calendar unavailable" description={error}/>:loading?<p className="data-note py-8">Loading event records…</p>:<DataTable<any> data={data?.events??[]} keyField="event_id" columns={[{key:'date',header:'Start date'},{key:'end_date',header:'End date'},{key:'category',header:'Category'},{key:'title',header:'Event',render:r=><span className="whitespace-normal block min-w-[240px] max-w-xl">{r.title}</span>},{key:'region',header:'Region'},{key:'severity',header:'Severity',render:r=><StatusBadge label={r.severity?.toUpperCase()??'UNCLASSIFIED'} variant={r.severity==='high'?'danger':r.severity==='medium'?'warning':'neutral'}/>},{key:'source',header:'Stored reference'}]}/>}
 <div className="flex items-center justify-between mt-4"><button className="control" disabled={loading||offset===0} onClick={()=>setOffset(Math.max(0,offset-50))}>Previous</button><span className="data-note">Page {Math.floor(offset/50)+1}</span><button className="control" disabled={loading||!data||offset+data.count>=data.total} onClick={()=>setOffset(offset+50)}>Next</button></div>
 </TerminalPanel>
 <p className="data-note">Severity and region are parsed from existing metadata. Unknown values remain unclassified. Source IDs are identifiers, not invented URLs. Event Automation and its disabled production collection are unchanged.</p>
 </div>;
}
