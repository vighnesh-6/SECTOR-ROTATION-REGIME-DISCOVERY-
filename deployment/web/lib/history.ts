import { numeric, VARIANTS } from './contracts';

export type HistoryRow = Record<string, any>;

/** Use a union of stored dates; absent observations stay null. */
export function individualNavHistory(rows: HistoryRow[]): HistoryRow[] {
  const dates = new Map<string, HistoryRow>();
  for (const row of rows) {
    if (!VARIANTS.includes(row.variant)) continue;
    if (!dates.has(row.date)) dates.set(row.date, { date: row.date, ...Object.fromEntries(VARIANTS.map(v => [v, null])) });
    dates.get(row.date)![row.variant] = numeric(row.net_nav);
  }
  return [...dates.values()].sort((a, b) => a.date.localeCompare(b.date));
}

export function regimeLabel(value: unknown): string {
  const id = numeric(value);
  return id !== null && Number.isInteger(id) && id >= 0 && id < 6 ? `R${id}` : 'Unavailable';
}

export function regimeStatus(row: HistoryRow): string {
  if (row.valid === false || regimeLabel(row.raw_argmax) === 'Unavailable' || regimeLabel(row.accepted_regime) === 'Unavailable' || typeof row.is_confident !== 'boolean') return 'Unavailable / invalid inference';
  if (!row.is_confident) return 'Incumbent retained - low confidence';
  return Number(row.raw_argmax) === Number(row.accepted_regime) ? 'Raw candidate accepted' : 'Stored accepted state differs from raw';
}

export function decisionStatus(value: unknown): string {
  return value === true ? 'Rebalance triggered' : value === false ? 'No rebalance triggered' : 'Decision unavailable';
}

export function executionStatus(row: HistoryRow): string {
  if (!row.execution_record_date) return 'No execution record';
  return row.execution_rebalance_executed === true ? 'Executed (simulation)' :
    row.execution_rebalance_executed === false ? 'Not executed (simulation)' : 'Execution flag unavailable';
}
