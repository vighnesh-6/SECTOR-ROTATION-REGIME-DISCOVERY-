'use client';
import { useState } from 'react';
import { TerminalPanel } from '@/components/ui/terminal-panel';
import { MetricTile } from '@/components/ui/metric-tile';
import { SectionHeader } from '@/components/ui/section-header';
import { DataTable,ColumnDef } from '@/components/ui/data-table';
import { EmptyState } from '@/components/ui/empty-state';
import { useApi } from '@/lib/use-api';
import { VARIANTS,SECTORS,pct,fmt,numeric } from '@/lib/contracts';
import { performance,curve,simulationSeries } from '@/lib/analytics';
import { ResearchChart } from '@/components/analytics/chart';
import { PeriodSelect,VariantSelect,Refresh } from '@/components/analytics/controls';
export default function PortfolioAnalyticsPage(){
 const [period,setPeriod]=useState('holdout'),[selected,setSelected]=useState('1B');
 const {data,error,loading,refresh}=useApi<any>('/api/v1/portfolios?period='+period);
 const series=simulationSeries(data),metrics=Object.entries(series).map(([variant,rows])=>({variant,...performance(rows)}));
 const selectedMetrics=performance(series[selected]??[]),holding=data?.latest_holdings?.find((r:any)=>r.variant===selected);
 const assets=[...SECTORS,'CASH'];
 const allocation=(series[selected]??[]).map(r=>({date:r.date,...Object.fromEntries(assets.map(s=>[s,numeric(r['w_post_'+s.toLowerCase()])===null?null:Number(r['w_post_'+s.toLowerCase()])*100]))}));
 const columns:ColumnDef<any>[]=[{key:'variant',header:'Strategy / benchmark'},{key:'count',header:'Sessions'},{key:'total_return',header:'Window return',align:'right',render:r=>pct(r.total_return)},{key:'cagr',header:'CAGR',align:'right',render:r=>pct(r.cagr)},{key:'volatility',header:'Ann. volatility',align:'right',render:r=>pct(r.volatility)},{key:'sharpe',header:'Sharpe (Rf 0%)',align:'right',render:r=>fmt(r.sharpe)},{key:'turnover',header:'Cumulative turnover',align:'right',render:r=>pct(r.turnover)}];
 return <div className="space-y-5">
  <SectionHeader title="Portfolio analytics" description="Four preserved configurations · net-of-cost simulation histories · two benchmarks" action={<Refresh loading={loading} onClick={refresh}/>}/>
  <div className="flex flex-wrap items-center justify-between gap-3"><PeriodSelect value={period} onChange={setPeriod}/><VariantSelect value={selected} onChange={setSelected}/></div>
  {error?<EmptyState title="Portfolio data unavailable" description={error} action={<Refresh loading={loading} onClick={refresh}/>}/>:loading?<p className="data-note py-12">Loading actual simulation records…</p>:<>
   <p className="data-note">Selected observations: {selectedMetrics?.start??'—'} ? {selectedMetrics?.end??'—'} ? {selectedMetrics?.count??0} return intervals. Research holdout ends 2026-09-18; later catch-up is a separate window.</p>
   <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><MetricTile label={selected+' · Window return'} value={pct(selectedMetrics?.total_return)}/><MetricTile label="Annualized growth" value={pct(selectedMetrics?.cagr)} subtitle="252-session compounding convention"/><MetricTile label="Maximum drawdown" value={pct(selectedMetrics?.max_drawdown)} subtitle="Within selected observations"/><MetricTile label="Latest stored NAV" value={fmt(holding?.net_nav,4)} subtitle={holding?`As of ${holding.date} · ${holding.period}`:'Unavailable'}/></div>
   <TerminalPanel title="Equity curves & benchmark comparison" subtitle="Rebased to 100 immediately before the selected window; first session return is included. Missing observations are not forward-filled."><ResearchChart data={curve(series)} keys={Object.keys(series)} label="Rebased strategy and benchmark equity curves"/></TerminalPanel>
   <TerminalPanel title="Performance in the selected window" subtitle="NAV-derived total return; sample volatility; arithmetic-return Sharpe with Rf=0%."><DataTable data={metrics} columns={columns} keyField="variant"/></TerminalPanel>
   <TerminalPanel title={selected+' · Realized allocation history'} subtitle="End-of-session simulation weights; these include market drift and differ from next-session targets."><ResearchChart data={allocation} keys={assets} stacked percent label="Realized sector and cash allocation history"/></TerminalPanel>
   <TerminalPanel title={selected+' · Latest stored holdings'} subtitle={holding?`Session ${holding.date}; independent of the chart window above.`:'No current holdings record'}>
    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">{assets.map(s=><MetricTile key={s} label={s} value={pct(holding?.['w_post_'+s.toLowerCase()],1)}/>)}</div>
   </TerminalPanel>
   <div className="grid gap-4 md:grid-cols-2"><TerminalPanel title="Template A · 1A / 1B"><p className="data-note">Fully invested sector template. 1A uses the frozen equal-weight rules; 1B uses inverse-volatility weights. Neither variant is labelled universally optimal.</p></TerminalPanel><TerminalPanel title="Template B · 2A / 2B"><p className="data-note">Frozen defensive template: cash floors are 30% in R1, 40% in R3 and 20% in R5. The R3 equal-weight exception is preserved in the strategy engine.</p></TerminalPanel></div>
  </>}
 </div>;
}
