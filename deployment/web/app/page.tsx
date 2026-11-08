'use client';
import Link from 'next/link';
import { TerminalPanel } from '@/components/ui/terminal-panel';
import { MetricTile } from '@/components/ui/metric-tile';
import { SectionHeader } from '@/components/ui/section-header';
import { StatusBadge } from '@/components/ui/status-badge';
import { DataTable } from '@/components/ui/data-table';
import { EmptyState } from '@/components/ui/empty-state';
import { useApi } from '@/lib/use-api';
import { pct,fmt,UNIVERSE } from '@/lib/contracts';
import { Refresh } from '@/components/analytics/controls';
export default function OverviewPage(){
  const health=useApi<any>('/api/v1/health',true),regime=useApi<any>('/api/v1/regime/latest'),port=useApi<any>('/api/v1/portfolios');
  const h=health.data,r=regime.data;
  return <div className="space-y-6">
    <SectionHeader title="Market & portfolio intelligence" description="Indian equity regimes, six-sector rotation and four systematic portfolios." action={<Refresh loading={health.loading||regime.loading||port.loading} onClick={()=>{health.refresh();regime.refresh();port.refresh();}}/>}/>
    <div className="grid gap-4 md:grid-cols-4">
      <MetricTile label="System status" value={health.loading?'Checking':h?.status??'Unavailable'} subtitle={h?.database?.connected?'Database reachable; see freshness checks below':'No healthy fallback state'}/>
      <MetricTile label="Latest market session" value={h?.database?.latest_candle_date} subtitle="Oldest latest date across eight indices"/>
      <MetricTile label="Accepted regime" value={r?`R${r.accepted_regime.id}`:null} subtitle={r?.accepted_regime.economic_name??(regime.error||'Loading inference')}/>
      <MetricTile label="Maximum posterior" value={pct(r?.accepted_regime.max_probability)} subtitle={r?(r.accepted_regime.is_confident?'Above acceptance threshold':'Incumbent retained under uncertainty'):'No substitute probability'}/>
    </div>
    {(health.error||h?.status!=='HEALTHY')&&!health.loading&&<div role="status" className="notice">{health.error||(h?.reasons||[]).join(' · ')}<p className="mt-2">{h?.freshness_policy}</p></div>}
    <div className="grid gap-4 lg:grid-cols-3">
      <TerminalPanel title="Causal regime probabilities" subtitle={r?`Inference session ${r.date} · ${r.period}`:'Waiting for valid inference'} className="lg:col-span-2">
        {regime.error?<EmptyState title="Regime data unavailable" description={regime.error}/>:regime.loading?<p className="data-note">Loading inference…</p>:<div className="space-y-4">{r?.probabilities.map((p:any)=><div key={p.id}><div className="flex justify-between gap-3 text-xs mb-2"><span>R{p.id} ? {p.name}</span><span className="font-mono">{pct(p.prob)}</span></div><div className="h-2 bg-terminal-secondary rounded"><div className="h-2 bg-emerald-400 rounded" style={{width:`${p.prob*100}%`}}/></div></div>)}</div>}
      </TerminalPanel>
      <TerminalPanel title="Canonical market universe" subtitle="Eight index series; no stock-level universe">
        <div className="space-y-3">{UNIVERSE.map(symbol=>{const row=h?.indices?.find((i:any)=>i.symbol===symbol);return <div key={symbol} className="flex justify-between gap-2 text-xs"><span>{symbol}</span><span className={row?.stale?'text-amber-500':'text-terminal-muted'}>{row?.latest_date??'—'}</span></div>;})}</div>
        <p className="data-note mt-5">NIFTY 50 is the benchmark. INDIA VIX is a risk input; the six sectors form the rotation universe.</p>
      </TerminalPanel>
    </div>
    <TerminalPanel title="Latest stored portfolio execution" subtitle="Simulation NAVs are research/execution telemetry, not brokerage account balances.">
      {port.error?<EmptyState title="Portfolio data unavailable" description={port.error}/>:port.loading?<p className="data-note">Loading portfolios…</p>:<DataTable<any> keyField="variant" data={port.data?.latest_holdings??[]} columns={[
        {key:'variant',header:'Variant'},{key:'date',header:'As of'},{key:'period',header:'Period'},
        {key:'net_nav',header:'Stored net NAV',align:'right',render:r=>fmt(r.net_nav,4)},
        {key:'net_return',header:'Daily net return',align:'right',render:r=>pct(r.net_return)},
        {key:'actual_turnover',header:'Daily turnover',align:'right',render:r=>pct(r.actual_turnover)}
      ]}/>}
    </TerminalPanel>
    <TerminalPanel title="Next-session target allocations" subtitle={r?`Signals at ${r.date} close; target weights are distinct from realized holdings.`:'No target signal available'}>
      <DataTable<any> keyField="variant" data={r?.current_allocations??[]} columns={[{key:'variant',header:'Variant'},{key:'holding_days_after',header:'Holding sessions'},...['nifty50','auto','bank','fmcg','it','metal','pharma','cash'].map(s=>({key:'w_'+s,header:s.toUpperCase(),render:(row:any)=>pct(row['w_'+s],1)}))]}/>
    </TerminalPanel>
    <div className="grid gap-3 md:grid-cols-3">{[['/portfolio-analytics','Performance & allocation','Compare aligned strategy and benchmark histories.'],['/regime-intelligence','Regime research','Inspect observed causal probabilities and frozen profiles.'],['/research-methodology','Research provenance','Review periods, definitions and source artifacts.']].map(([href,title,text])=><Link key={href} href={href} className="rounded border border-terminal-border bg-terminal-panel p-5 hover:border-emerald-500 transition-colors"><h3 className="font-semibold text-sm">{title} ?</h3><p className="data-note mt-2">{text}</p></Link>)}</div>
  </div>;
}
