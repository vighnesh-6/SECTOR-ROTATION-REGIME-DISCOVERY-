import { NextResponse } from 'next/server';
import { validDate } from './contracts';
export class InputError extends Error {}
export function integer(value: string | null, fallback: number, min: number, max: number): number {
  if (value === null) return fallback;
  if (!/^\d+$/.test(value) || Number(value) < min || Number(value) > max) throw new InputError(`Expected an integer between ${min} and ${max}.`);
  return Number(value);
}
export function dates(params: URLSearchParams, start: string, end: string) {
  const from = params.get('from_date') ?? start, to = params.get('to_date') ?? end;
  if (!validDate(from) || !validDate(to) || from > to) throw new InputError('Supply an ordered date range in YYYY-MM-DD format.');
  return {from,to};
}
export function apiError(error: unknown) {
  return NextResponse.json({error: error instanceof InputError ? error.message : 'Data service unavailable. Retry later; no substitute data has been used.'}, {status: error instanceof InputError ? 400 : 503});
}
