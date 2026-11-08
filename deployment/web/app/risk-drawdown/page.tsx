'use client';
import { useState } from 'react';
import { TerminalPanel } from '@/components/ui/terminal-panel';
import { MetricTile } from '@/components/ui/metric-tile';
import { SectionHeader } from '@/components/ui/section-header';
import { DataTable } from '@/components/ui/data-table';
import { EmptyState } from '@/components/ui/empty-state';
import { useApi } from '@/lib/use-api';
import { pct,fmt } from '@/lib/contracts';
import { performance,curve,simulationSeries } from '@/lib/analytics';
import { ResearchChart } from '@/components/analytics/chart';
import { PeriodSelect,Refresh } from '@/components/analytics/controls';
export default function RiskDrawdownPage(){
 const [period,setPeriod]=useState('holdout');const {data,error,loading,refresh}=useApi<any>('/api/v1/portfolios?period='+period);
 const series=simulationSeries(data),rows=Object.entries(series).map(([variant,r])=>({variant,...performance(r)}));
 return <div className="space-y-5">
  <SectionHeader title="Risk & drawdown" description="Realized simulation risk, evaluated on the same windows and definitions as Portfolio Analytics." action={<Refresh onClick={refresh} loading={loading}/>}/>
  <PeriodSelect value={period} onChange={setPeriod}/>
  {error?<EmptyState title="Risk data unavailable" description={error}/>:loading?<p className="data-note py-12">Loading observed daily returns…</p>:<>
  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{['1A','1B','2A','2B'].map(v=><MetricTile key={v} label={v+' · Maximum drawdown'} value={pct(rows.find(r=>r.variant===v)?.max_drawdown)} subtitle="Selected window; not an all-history claim"/>)}</div>
  <TerminalPanel title="Underwater curves" subtitle="Drawdown from the running peak within selected observations; same convention as the research engine."><ResearchChart data={curve(series,true)} keys={Object.keys(series)} percent label="Strategy and benchmark historical drawdowns" yLabel="Drawdown from peak (%)"/></TerminalPanel>
  <TerminalPanel title="Realized risk comparison" subtitle="Signed daily return quantiles: negative values indicate losses. No invented downside variance or default 6% risk-free rate.">
  <DataTable data={rows} keyField="variant" columns={[{key:'variant',header:'Strategy / benchmark'},{key:'count',header:'Sessions'},...['max_drawdown','volatility','var95','cvar95'].map(k=>({key:k,header:({max_drawdown:'Max drawdown',volatility:'Ann. volatility',var95:'Daily 5% quantile',cvar95:'Mean 5% tail'} as Record<string,string>)[k],render:(r:any)=>pct(r[k])})),{key:'sharpe',header:'Sharpe (Rf=0%)',render:r=>fmt(r.sharpe)},{key:'sortino',header:'Sortino (MAR=0%)',render:r=>fmt(r.sortino)}]}/>
  </TerminalPanel>
  <TerminalPanel title="Metric definitions & limits"><div className="grid gap-4 md:grid-cols-2 text-sm text-terminal-muted leading-relaxed"><p>Annualization uses 252 return intervals. Volatility is the sample standard deviation (ddof=1). Sharpe uses annualized arithmetic mean return with zero risk-free rate. Sortino uses all observations in its downside-deviation denominator with MAR=0.</p><p>Total return and CAGR use the actual pre-window NAV, including the first session. Drawdown starts with the first selected observed NAV. Empirical tail risk uses the sorted daily returns at floor(0.05 · N). Undefined ratios display unavailable; the frozen research results remain unchanged.</p></div></TerminalPanel>
  </>}
 </div>;
}
