export const SERIES_COLORS: Record<string, string> = {
  '1A': '#34d399', '1B': '#60a5fa', '2A': '#fbbf24', '2B': '#c084fc',
  AUTO: '#fbbf24', BANK: '#60a5fa', FMCG: '#34d399', IT: '#22d3ee',
  METAL: '#fb923c', PHARMA: '#c084fc', CASH: '#94a3b8',
  R0: '#34d399', R1: '#fbbf24', R2: '#60a5fa', R3: '#fb7185', R4: '#22d3ee', R5: '#c084fc',
  NIFTY50_BUY_HOLD: 'var(--sector-benchmark)',
  EQUAL_WEIGHT_6SECTOR: '#fb7185', EQUAL_WEIGHT_6_SECTOR: '#fb7185', EQUAL_WEIGHT_BUY_HOLD: '#fb7185',
};
const NAMES: Record<string, string> = {
  '1A': '1A - Template A / equal weight', '1B': '1B - Template A / inverse volatility',
  '2A': '2A - Template B / equal weight', '2B': '2B - Template B / inverse volatility',
  NIFTY50_BUY_HOLD: 'NIFTY 50 buy & hold', EQUAL_WEIGHT_6SECTOR: 'Six-sector equal-weight benchmark', EQUAL_WEIGHT_6_SECTOR: 'Six-sector equal-weight benchmark',
  EQUAL_WEIGHT_BUY_HOLD: 'Six-sector equal-weight benchmark',
  R0: 'R0 - Cyclical reflation', R1: 'R1 - Post-crash bounce', R2: 'R2 - Consolidation',
  R3: 'R3 - Acute liquidation', R4: 'R4 - Steady expansion', R5: 'R5 - Correction',
};
export function chartSeries(key: string) {
  return { label: NAMES[key] ?? key.replace(/_/g, ' '), color: SERIES_COLORS[key] ?? '#94a3b8' };
}
