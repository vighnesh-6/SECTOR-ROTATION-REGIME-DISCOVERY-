'use client';
import {useState} from 'react';
import { TerminalPanel } from '@/components/ui/terminal-panel';
import { MetricTile } from '@/components/ui/metric-tile';
import { SectionHeader } from '@/components/ui/section-header';
import { DataTable } from '@/components/ui/data-table';
import { ResearchChart } from '@/components/analytics/chart';
import {pct,fmt} from '@/lib/contracts';
import research from '@/lib/research-artifacts.json';
export default function EventIntelligencePage(){
 const [episodeId,setEpisodeId]=useState(research.event_episodes[0]?.episode_id??'');
 const episode=research.event_episodes.find(e=>e.episode_id===episodeId);
 const meta=research.event_metadata.filter(e=>e.episode_id===episodeId);
 const sectors=research.event_sectors.map(r=>({...r,event_excess:r.event_annualized_excess_return*100,normal_excess:r.normal_annualized_excess_return*100}));
 const episodeRows=episode?(['1A','1B','2A','2B'] as const).map(variant=>({variant,return:episode[('ret_'+variant) as keyof typeof episode],drawdown:episode[('mdd_'+variant) as keyof typeof episode],turnover:episode[('turnover_'+variant) as keyof typeof episode]})):[];
 return <div className="space-y-5">
 <SectionHeader title="Event intelligence" description="Frozen empirical event study · descriptive association, not a causal forecast or trading signal"/>
 <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><MetricTile label="Event-day observations" value={sectors[0]?.n_event_days} subtitle="Frozen sector study sample"/><MetricTile label="Normal-day observations" value={sectors[0]?.n_normal_days}/><MetricTile label="Recorded macro episodes" value={research.event_episodes.length}/><MetricTile label="Research event definitions" value={research.event_metadata.length} subtitle="Distinct from the current Neon calendar count"/></div>
 <TerminalPanel title="Sector behavior on event and normal days" subtitle="Annualized arithmetic excess returns versus NIFTY 50; grouping from the frozen study, not expected future returns.">
 <DataTable keyField="sector" data={sectors} columns={[{key:'sector',header:'Sector'},{key:'event_annualized_excess_return',header:'Event excess (ann.)',render:r=>pct(r.event_annualized_excess_return)},{key:'normal_annualized_excess_return',header:'Normal excess (ann.)',render:r=>pct(r.normal_annualized_excess_return)},{key:'event_volatility_annualized',header:'Event volatility',render:r=>pct(r.event_volatility_annualized)},{key:'normal_volatility_annualized',header:'Normal volatility',render:r=>pct(r.normal_volatility_annualized)},{key:'event_win_rate_vs_benchmark',header:'Event win rate',render:r=>fmt(r.event_win_rate_vs_benchmark)+'%'}]}/>
 </TerminalPanel>
 <TerminalPanel title="Artifact-backed macro episode explorer" subtitle="Overlapping catalysts are grouped into episodes. Returns use the study's recorded episode sessions; no invented T+10 case-study figures." headerRight={<label className="text-xs">Episode <select className="control max-w-[240px]" value={episodeId} onChange={e=>setEpisodeId(e.target.value)}>{research.event_episodes.map(e=><option key={e.episode_id} value={e.episode_id}>{e.episode_id} ? {e.start_date.slice(0,10)} ? {e.primary_macro_category}</option>)}</select></label>}>
 {episode&&<><div className="grid gap-3 md:grid-cols-3 mb-4"><MetricTile label="Episode anchors" value={episode.start_date.slice(0,10)} subtitle={'Through '+episode.end_date.slice(0,10)}/><MetricTile label="Unique event-window sessions" value={episode.n_unique_sessions} subtitle={episode.event_count+' overlapping event definitions'}/><MetricTile label="NIFTY 50 episode return" value={pct(episode.market_return)} subtitle={'Episode drawdown '+pct(episode.market_mdd)}/></div><DataTable keyField="variant" data={episodeRows} columns={[{key:'variant',header:'Variant'},{key:'return',header:'Episode net return',render:r=>pct(r.return)},{key:'drawdown',header:'Episode drawdown',render:r=>pct(r.drawdown)},{key:'turnover',header:'Episode turnover',render:r=>pct(r.turnover)}]}/><ul className="mt-4 space-y-2 text-xs text-terminal-muted">{meta.map(m=><li key={m.event_id}>{m.event_id} ? {m.event_name} ? {m.start_date.slice(0,10)}</li>)}</ul></>}
 </TerminalPanel>
 <p className="data-note">Sources: results/event_analysis/sector_performance_during_events.csv, macro_episodes_summary.parquet and event_metadata_authoritative.parquet. Source SHA256s are recorded in the website research snapshot. Association and episode returns do not establish causation or guaranteed protection.</p>
 </div>;
}
