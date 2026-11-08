export const SECTORS = ['AUTO', 'BANK', 'FMCG', 'IT', 'METAL', 'PHARMA'] as const;
export const UNIVERSE = ['NIFTY 50', ...SECTORS.map(s => `NIFTY ${s}`), 'INDIA VIX'];
export const VARIANTS = ['1A', '1B', '2A', '2B'] as const;
export const REGIME_NAMES = ['Cyclical Reflation Rally', 'High-Volatility Post-Crash Bounce', 'Low-Volatility Consolidation / Base', 'Acute Liquidation / Flight to Safety', 'Steady Expansion / Low-Volatility Bull', 'Correction / Risk-Off Digestion'];
export function numeric(value: unknown): number | null {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null;
  const n = Number(value); return Number.isFinite(n) ? n : null;
}
export function fmt(value: unknown, digits = 2): string { const n = numeric(value); return n === null ? '—' : n.toFixed(digits); }
export function pct(value: unknown, digits = 2): string { const n = numeric(value); return n === null ? '—' : `${(n * 100).toFixed(digits)}%`; }
export function validDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value)) && new Date(`${value}T00:00:00Z`).toISOString().slice(0,10) === value;
}
export function validInference(row: Record<string, unknown> | undefined): boolean {
  if (!row) return false;
  const probs = Array.from({length:6}, (_, i) => numeric(row[`prob_${i}`]));
  const id = numeric(row.accepted_regime), max = numeric(row.max_probability), raw = numeric(row.raw_argmax);
  return probs.every(p => p !== null && p >= 0 && p <= 1) && Math.abs(probs.reduce<number>((a,p) => a+(p ?? 0),0)-1) < 1e-5
    && id !== null && Number.isInteger(id) && id >= 0 && id < 6 && raw !== null && Number.isInteger(raw) && raw >= 0 && raw < 6
    && max !== null && Math.abs(Math.max(...probs as number[])-max) < 1e-5 && Math.abs((probs[raw] ?? -1)-max) < 1e-5
    && typeof row.is_confident === 'boolean' && row.is_confident === (max >= 0.5);
}
export function metadata(value: unknown, prefix: string): string | null {
  if (typeof value !== 'string') return null;
  const result = value.replace(new RegExp(`^${prefix}:\\s*`,'i'),'').trim(); return result || null;
}
export function severity(value: unknown): string | null {
  const s = metadata(value,'Severity')?.toLowerCase(); return s && ['high','medium','low'].includes(s) ? s : null;
}
