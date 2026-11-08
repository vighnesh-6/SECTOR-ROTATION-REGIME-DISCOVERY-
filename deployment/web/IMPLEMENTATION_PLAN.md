# Existing website audit and implementation plan

Scope: retain Next.js App Router, the eight existing page routes, Tailwind themes,
terminal components, Recharts, Neon tables and four strategy variants. Only website
files change. Research, model/strategy code, both automation workflows, event
automation, environment files and all database records are protected.

## Audit findings

- Header/footer imply healthy live connectivity even when requests fail.
- Health ignores stale/inconsistent dates and can select event logs as Market EOD.
- RRG UI reads `ratio`/`momentum`; API emits `rs_ratio`/`rs_momentum`. Missing closes
  become fabricated relative strength 1.0. There is no query parameter validation.
- Portfolio page hardcodes NAVs and dates, labels filtered data as inception, and
  expects return/turnover fields absent from latest holdings. No equity/history charts.
- Risk uses an unverified 6% risk-free rate, inconsistent with research Sharpe;
  single-point/zero-downside cases invent numerical values.
- Regime page hardcodes mean durations/VIX ranges and incorrect Template B cash
  floors (research specifies R1 30%, R3 40%, R5 20%). It defaults to active R0 on error.
- Event study sector numbers are copied constants; shock-case returns lack artifact
  links. Calendar assumes severity is a non-null string and labels limited rows total.
- Methodology includes unsupported significance/robustness claims and ambiguous dates.
- Neon environment fallback can accidentally match EVENT_TEST_DATABASE_URL as
  DATABASE_URL; raw database errors can leak response text.

## Page-wise sequence

1. Contracts/data foundation: validated read-only APIs, bounded parameters, safe errors,
   actual per-symbol freshness, valid probability vectors and aligned date ranges.
   Create a website research snapshot from existing artifacts with source SHA256s.
2. Overview `/`: independent error/loading states, actual session/regime/allocation
   telemetry, explicit freshness and canonical eight-index universe.
3. Sector Rotation `/sector-rotation`: repair existing SVG field contract, use only
   complete aligned candles, document standardized relative-strength methodology.
4. Portfolios `/portfolio-analytics`: four preserved variants; explicit full/train/
   research-holdout/post-research date filters; rebased equity and benchmark chart,
   realized return/turnover table, allocation history and current holdings.
5. Risk `/risk-drawdown`: same selected window and metric function; drawdown chart,
   sample-volatility/zero-rf Sharpe conventions matching frozen research, explicit
   undefined values and empirical tail risk.
6. Regimes `/regime-intelligence`: actual latest probabilities/history; artifact-backed
   causal profiles split by research period, sample-size caveats, canonical rules.
7. Events `/event-intelligence`: source-backed frozen event study; remove unverified
   shock returns, distinguish retrospective association from causal forecasts.
8. Calendar `/economic-calendar`: safe metadata normalization, dynamic categories,
   server-side filters/pagination and correct counts; no collector changes.
9. Methodology `/research-methodology`: sourced model/strategy/period specifications,
   honest holdout results and provenance; no unsupported significance claims.

## Verification

Run meaningful numerical/API regression tests; TypeScript and production build;
exercise all eight routes and every API against the isolated Neon branch via
SELECT-only requests. Inspect responsive browser charts and failed/empty states.
Compare protected file hashes and database snapshots before/after. No production
write, backfill, workflow enablement, commit, push or hosted-deployment claim.

Read-only database audit: 2019-01-02 candle inception; 2019-10-31 inference start;
2019-11-01 simulation start; research holdout 2025-01-02..2026-09-18; subsequent
catch-up 2026-09-21..2026-11-06. These are different periods, not interchangeable.
