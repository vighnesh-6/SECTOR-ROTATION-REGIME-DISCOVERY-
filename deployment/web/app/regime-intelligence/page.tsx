'use client';
import {useState} from 'react';
import { TerminalPanel } from '@/components/ui/terminal-panel';
import { MetricTile } from '@/components/ui/metric-tile';
import { SectionHeader } from '@/components/ui/section-header';
import { DataTable } from '@/components/ui/data-table';
import { EmptyState } from '@/components/ui/empty-state';
import { ResearchChart } from '@/components/analytics/chart';
import { Refresh } from '@/components/analytics/controls';
import { useApi } from '@/lib/use-api';
import {pct,fmt,REGIME_NAMES} from '@/lib/contracts';
import research from '@/lib/research-artifacts.json';
export default function RegimeIntelligencePage(){
 const [profilePeriod,setProfilePeriod]=useState('holdout'),[historyPeriod,setHistoryPeriod]=useState('holdout');
 const dates:Record<string,string>={holdout:'from_date=2025-01-02&to_date=2026-09-18',full:'from_date=2019-10-31',post:'from_date=2026-09-21'};
 const latest=useApi<any>('/api/v1/regime/latest'),history=useApi<any>('/api/v1/regime/history?'+dates[historyPeriod]);
 const profiles=research.regime_profiles.filter(r=>r.period===profilePeriod);
 return <div className="space-y-5">
 <SectionHeader title="Regime intelligence" description="Six-state Gaussian HMM · stored causal inference · frozen research characterization" action={<Refresh loading={latest.loading||history.loading} onClick={()=>{latest.refresh();history.refresh();}}/>}/>
 {latest.error?<EmptyState title="Latest regime unavailable" description={latest.error}/>:<div className="grid gap-4 md:grid-cols-4"><MetricTile label="Accepted regime" value={latest.data?`R${latest.data.accepted_regime.id}`:null} subtitle={latest.data?.accepted_regime.economic_name}/><MetricTile label="Maximum posterior" value={pct(latest.data?.accepted_regime.max_probability)} subtitle={latest.data?.date}/><MetricTile label="Acceptance threshold" value={pct(research.rules.confidence_threshold)} subtitle="Frozen confidence rule"/><MetricTile label="Minimum holding" value={research.rules.minimum_holding_sessions+' sessions'} subtitle="R3 crisis bypass; execution remains T+1"/></div>}
 <TerminalPanel title="Historical causal probabilities" subtitle="Actual stored probabilities; gaps and invalid observations are not interpolated." headerRight={<label className="text-xs">History window <select className="control" value={historyPeriod} onChange={e=>setHistoryPeriod(e.target.value)}><option value="holdout">Research holdout</option><option value="full">All inference history</option><option value="post">Post-research</option></select></label>}>
 {history.error?<EmptyState title="History unavailable" description={history.error}/>:history.loading?<p className="data-note">Loading probability history…</p>:<><ResearchChart data={(history.data?.history??[]).map((r:any)=>({...r,...Object.fromEntries(Array.from({length:6},(_,i)=>[`R${i}`,r[`R${i}`]===null?null:r[`R${i}`]*100]))}))} keys={REGIME_NAMES.map((_,i)=>'R'+i)} percent label="Historical causal HMM regime probabilities"/>{history.data?.invalid_rows>0&&<p role="alert" className="notice">{history.data.invalid_rows} invalid inference rows are shown as gaps.</p>}</>}
 </TerminalPanel>
 <TerminalPanel title="Frozen causal regime profiles" subtitle="Observed research statistics; these are not forecasts of duration or volatility." headerRight={<label className="text-xs">Research sample <select className="control" value={profilePeriod} onChange={e=>setProfilePeriod(e.target.value)}><option value="holdout">Holdout</option><option value="train">Training</option></select></label>}>
 <DataTable keyField="regime_id" data={profiles} columns={[{key:'regime_id',header:'Regime',render:r=>'R'+r.regime_id},{key:'economic_name',header:'Characterization'},{key:'n_trading_days',header:'Observed sessions'},{key:'n_episodes',header:'Episodes'},{key:'mean_duration_days',header:'Mean duration',render:r=>r.n_trading_days?fmt(r.mean_duration_days,1):'—'},{key:'vix_close_mean',header:'Mean INDIA VIX',render:r=>r.n_trading_days?fmt(r.vix_close_mean):'—'},{key:'cash',header:'Template B cash floor',render:r=>pct(research.rules.template_b_cash[r.regime_id],0)}]}/>
 <div className="grid gap-3 md:grid-cols-2 mt-4">{profiles.map(r=><div key={r.regime_id} className="rounded border border-terminal-border p-4"><h3 className="text-sm font-semibold">R{r.regime_id} ? {r.economic_name}</h3><p className="data-note mt-2">{r.description}</p><p className="text-xs text-amber-600 dark:text-amber-400 mt-3">{r.caveats}</p><p className="data-note mt-3">Authorized sectors: {research.rules.regime_sectors[r.regime_id].join(' / ')}</p></div>)}</div>
 </TerminalPanel>
 <p className="data-note">Source: results/regime_characterization/regime_profiles/model_regime_profiles.csv · HMM filtered_causal rows only. Raw causal state characterization differs from the confidence/holding-gated accepted regime.</p>
 </div>;
}
