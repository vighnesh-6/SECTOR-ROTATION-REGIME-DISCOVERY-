'use client';
import { TerminalPanel } from '@/components/ui/terminal-panel';
import { HistoryTable } from './history-table';
import { pct } from '@/lib/contracts';
import { regimeLabel, regimeStatus, HistoryRow } from '@/lib/history';

export function RegimeHistory({ rows }: { rows: HistoryRow[] }) {
  return <TerminalPanel title="Daily raw-predicted and accepted regime history"
    subtitle="Observed same-session causal classifications, not next-day forecasts or externally confirmed ground truth.">
    <HistoryTable rows={[...rows].reverse()} rowKey="date" columns={[
      { key: 'date', header: 'Session' }, { key: 'period', header: 'Stored period' },
      { key: 'raw_argmax', header: 'Raw predicted regime', render: row => regimeLabel(row.raw_argmax) },
      { key: 'accepted_regime', header: 'Accepted regime', render: row => regimeLabel(row.accepted_regime) },
      { key: 'max_probability', header: 'Raw maximum posterior', render: row => pct(row.max_probability, 4) },
      { key: 'accepted_probability', header: 'Accepted-state posterior', render: row => pct(row.accepted_probability, 4) },
      { key: 'is_confident', header: 'Stored confidence flag', render: row => row.is_confident === true ? 'Confident' : row.is_confident === false ? 'Not confident' : 'Unavailable' },
      { key: 'status', header: 'Regime status', render: row => regimeStatus(row) },
      { key: 'valid', header: 'Data validity', render: row => row.valid === true ? 'Valid' : 'Invalid / unavailable' },
    ]} />
    <p className="data-note mt-4">Raw prediction is the stored argmax. Acceptance reflects the stored model acceptance result; a portfolio may retain a different incumbent under its existing holding rules. Portfolio decisions and simulation execution appear separately in Portfolio Analytics.</p>
  </TerminalPanel>;
}
