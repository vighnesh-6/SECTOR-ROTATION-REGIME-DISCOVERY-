'use client';
import { useState } from 'react';
import { TerminalPanel } from '@/components/ui/terminal-panel';
import { MetricTile } from '@/components/ui/metric-tile';
import { DataTable } from '@/components/ui/data-table';
import { EmptyState } from '@/components/ui/empty-state';
import { Refresh } from './controls';
import { ResearchChart } from './chart';
import { HistoryTable } from './history-table';
import { useApi } from '@/lib/use-api';
import { numeric, pct, fmt, VARIANTS } from '@/lib/contracts';
import { individualNavHistory, regimeLabel, regimeStatus, decisionStatus, executionStatus, HistoryRow } from '@/lib/history';
import { chartSeries } from '@/lib/chart-series';

export function PortfolioHistory({ variant, fromDate, toDate }: {
  variant: string; fromDate: string; toDate: string;
}) {
  const [sessions, setSessions] = useState('15');
  const [scope, setScope] = useState('selected');
  const query = new URLSearchParams({ from_date: fromDate, to_date: toDate, recent_sessions: sessions });
  const { data, error, loading, refresh } = useApi<any>('/api/v1/portfolios/history?' + query);
  const nav = individualNavHistory(data?.recent_nav ?? []);
  const turnover: HistoryRow[] = (data?.turnover_history ?? []).filter((row: HistoryRow) => row.variant === variant);
  const decisions: HistoryRow[] = (data?.rebalance_history ?? []).filter((row: HistoryRow) => row.variant === variant);
  const last = turnover[turnover.length - 1];
  const cumulativeKey = scope === 'selected' ? 'cumulative_selected_period' : 'cumulative_all_history';
  const percentValue = (value: unknown) => numeric(value) === null ? null : Number(value) * 100;
  const turnoverChart = turnover.map(row => ({
    date: row.date, daily_actual: percentValue(row.actual_turnover),
    cumulative: percentValue(row[cumulativeKey]),
  }));
  const color = chartSeries(variant).color;
  return <div className="space-y-5">
    <div className="flex flex-wrap justify-between items-center gap-3">
      <p className="data-note">Stored NAV, turnover and rebalance records. No inference or simulation is rerun.</p>
      <Refresh loading={loading} onClick={refresh} />
    </div>
    {error ? <EmptyState title="Stored portfolio history unavailable" description={error} /> :
      loading ? <p className="data-note py-8">Loading stored portfolio history...</p> : <>
      <TerminalPanel title="Individual Net NAV - recent trading sessions"
        subtitle={`Latest ${data?.recent_sessions_returned ?? 0} stored simulation dates across all variants; independent of the evaluation window. Original NAV units, not rebased to 100.`}
        headerRight={<label className="text-xs">Recent sessions <select className="control" value={sessions} onChange={e => setSessions(e.target.value)}>
          <option value="10">10 sessions</option><option value="15">15 sessions</option>
        </select></label>}>
        <ResearchChart data={nav} keys={[...VARIANTS]} label="Individual stored Net NAV for four portfolio variants"
          yLabel="Net NAV (stored units)" decimals={4} tooltipDecimals={6} points />
        <div className="mt-5"><DataTable<any> keyField="date" data={[...nav].reverse()} columns={[
          { key: 'date', header: 'Trading session' },
          ...VARIANTS.map(v => ({ key: v, header: v + ' Net NAV', render: (row: HistoryRow) => fmt(row[v], 6) })),
        ]} /></div>
        <p className="data-note mt-3">Only observed dates are shown. A missing variant observation stays unavailable; values are never forward-filled.</p>
      </TerminalPanel>

      <TerminalPanel title={variant + ' - Daily and cumulative actual turnover'}
        subtitle={`Selected evaluation records: ${turnover[0]?.date ?? 'unavailable'} to ${last?.date ?? 'unavailable'}. Percentages express the stored turnover fraction times 100.`}
        headerRight={<label className="text-xs">Cumulative scope <select className="control" value={scope} onChange={e => setScope(e.target.value)}>
          <option value="selected">Selected period to date</option><option value="all">All history to date</option>
        </select></label>}>
        <div className="grid gap-3 sm:grid-cols-3 mb-5">
          <MetricTile label="Latest daily actual turnover in window" value={pct(last?.actual_turnover)} subtitle={last?.date} />
          <MetricTile label="Selected-period cumulative turnover" value={pct(last?.cumulative_selected_period)} subtitle="Inclusive sum within selected window" />
          <MetricTile label="All-history cumulative at window end" value={pct(last?.cumulative_all_history)} subtitle={last ? 'Through ' + last.date + '; excludes later sessions' : 'No observed scope'} />
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          <ResearchChart data={turnoverChart} keys={['daily_actual']} percent points
            label={variant + ' daily actual turnover'} yLabel="Daily turnover (%)"
            series={{ daily_actual: { label: variant + ' daily actual turnover', color } }} />
          <ResearchChart data={turnoverChart} keys={['cumulative']} percent
            label={variant + ' cumulative actual turnover'} yLabel="Cumulative turnover (%)"
            series={{ cumulative: { label: variant + (scope === 'selected' ? ' selected-period cumulative' : ' all-history cumulative to date'), color, dash: scope === 'all' ? '5 3' : undefined } }} />
        </div>
        <p className="data-note my-4">Selected-period cumulative = sum of stored daily actual turnover from the selected start through each date. All-history cumulative = sum from the first stored simulation through that date, including earlier periods but excluding later dates. Sums are not compounded or averaged; unavailable inputs keep the affected cumulative value unavailable.</p>
        <HistoryTable key={variant + fromDate + toDate} rows={[...turnover].reverse()} rowKey="date" columns={[
          { key: 'date', header: 'Session' },
          { key: 'actual_turnover', header: 'Daily actual turnover', render: row => pct(row.actual_turnover, 4) },
          { key: 'cumulative_selected_period', header: 'Cumulative selected period', render: row => pct(row.cumulative_selected_period, 4) },
          { key: 'cumulative_all_history', header: 'Cumulative all history to date', render: row => pct(row.cumulative_all_history, 4) },
        ]} />
      </TerminalPanel>

      <TerminalPanel title={variant + ' - Regime acceptance, rebalance decision and execution'}
        subtitle="Signal date and scheduled execution date are separate. An accepted market regime does not itself prove a portfolio rebalance or execution.">
        <HistoryTable key={variant + fromDate + toDate} rows={[...decisions].reverse()} rowKey="signal_date" columns={[
          { key: 'signal_date', header: 'Signal date' },
          { key: 'raw_argmax', header: 'Raw predicted state', render: row => regimeLabel(row.raw_argmax) },
          { key: 'accepted_regime', header: 'Accepted market state', render: row => regimeLabel(row.accepted_regime) },
          { key: 'max_probability', header: 'Max posterior', render: row => pct(row.max_probability) },
          { key: 'confirmation', header: 'Model acceptance status', render: row => regimeStatus(row) },
          { key: 'incumbent', header: 'Portfolio incumbent before / after', render: row => regimeLabel(row.incumbent_regime_before) + ' / ' + regimeLabel(row.incumbent_regime_after) },
          { key: 'holding_days_after', header: 'Stored holding sessions' },
          { key: 'decision', header: 'Portfolio decision', render: row => decisionStatus(row.rebalance_triggered) },
          { key: 'rebalance_bypassed_r3', header: 'Stored crisis bypass', render: row => row.rebalance_bypassed_r3 === true ? 'Yes' : row.rebalance_bypassed_r3 === false ? 'No' : 'Unavailable' },
          { key: 'decision_turnover', header: 'Decision turnover', render: row => pct(row.decision_turnover) },
          { key: 'scheduled_execution_date', header: 'Scheduled date' },
          { key: 'execution_status', header: 'Recorded execution status', render: row => executionStatus(row) },
          { key: 'execution_record_date', header: 'Execution record date' },
          { key: 'actual_execution_date', header: 'Actual simulation execution date' },
          { key: 'execution_actual_turnover', header: 'Recorded daily actual turnover on scheduled date', render: row => pct(row.execution_actual_turnover, 4) },
        ]} />
        <p className="data-note mt-4">Execution is read from the same variant's simulation on the stored scheduled date. Missing records are not marked executed; a stored false flag is reported as not executed even if a decision was triggered. These are simulation records, not broker fills. No confirmation threshold, holding rule or execution schedule is recalculated.</p>
      </TerminalPanel>
    </>}
  </div>;
}
