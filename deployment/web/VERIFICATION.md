# Website improvement verification - 2026-11-08 IST

Implemented in the existing Next.js 15 App Router website. The eight page routes,
Tailwind themes, terminal components, existing Recharts dependency and Neon tables
are retained. No replacement website/framework, database migration or strategy
change was introduced. Implementation plan: IMPLEMENTATION_PLAN.md.

## Implemented behavior

- Overview/header/footer: remove fabricated healthy states, fixed dates/latencies
  and unverified portfolio values. Report actual per-index/inference/portfolio
  freshness. Event logs cannot masquerade as a successful Market EOD execution.
- RRG: repair API/UI trail fields, align all seven required price series, remove
  missing-price substitutions and fixed plot clipping. Keep the existing
  descriptive standardized-strength formula; do not change portfolio selection.
- Portfolios/risk: actual daily return and turnover fields, pre-window NAV baselines,
  equity/benchmark curves, underwater curves and realized allocation history.
  Shared definitions preserve research conventions and first-session accounting.
- Explicit windows: training, frozen research holdout, post-research catch-up and
  full simulation history. Candle, inference and simulation inception differ.
- Regimes: actual latest and historical causal probabilities, invalid-row gaps,
  artifact-backed train/holdout profiles, sparse-sample caveats and correct cash floors.
- Event Intelligence: replace unverified shock returns with frozen episode records;
  copy empirical study artifacts with source SHA256s instead of editable constants.
- Calendar: bounded parameterized pagination, dynamic category filters, actual totals,
  nullable metadata and no invented release timestamps or source URLs.
- Methodology: explicit source provenance, frozen rule specifications and actual
  negative holdout results; remove unsupported universal significance claims.
- Website database client: exact environment key matching, SELECT-only query guard,
  bounded transient retries/timeouts and generic errors without upstream secrets.

## Actual checks

- npm test: 21 numerical/API regression tests passed.
- npm run typecheck: passed.
- npm run build: passed; all eight pages and six dynamic API routes built.
- node tests/live-check.cjs: passed against the final built local preview.
  Eight pages returned HTTP 200; 44 API requests returned expected statuses,
  including every calendar category and invalid-input HTTP 400 cases.
- Six metrics (total return, CAGR, volatility, Sharpe, Sortino, max drawdown) for
  each of four variants across training and holdout matched frozen metrics within
  1e-5 absolute tolerance. Counts: 1264 training and 422 holdout return intervals.
- All 10 research snapshot provenance hashes match their untouched source files.
- git diff --check: passed.
- Existing lint command retained. No new ESLint configuration/dependencies added;
  TypeScript checks are reported separately, not misrepresented as an ESLint audit.

Machine-readable HTTP/metric evidence: tests/live-results.json.
Deterministic numerical/API suite: tests/analytics.test.cjs and tests/api.test.cjs.
The opt-in HTTP integration script accepts only a local preview URL. It does not
load credentials or run database write queries.

## Data and protected-file verification

Only the isolated Neon branch br-odd-star-a1hjl6dl (the previously confirmed
 event-automation-test branch), endpoint ep-cold-wind-a14dq44q, was used for website
integration. Its identity was verified before tests. The connection was loaded
from deployment/.env.local into the local server's process memory, overriding
website connection variables without changing files. No production access.

All nine table fingerprints and row counts match the pre-test snapshots:

| Table | Rows unchanged |
| --- | ---: |
| index_candles_daily | 15352 |
| market_features_daily | 33 |
| regime_inference_daily | 1720 |
| portfolio_allocations_daily | 6880 |
| portfolio_simulations_daily | 6876 |
| benchmark_simulations_daily | 3438 |
| macro_events | 230 |
| pipeline_execution_logs | 2 |
| reconciliation_audit_logs | 0 |

No test fixtures, production writes, historical backfill or schema changes.
231 protected files were compared before/after with identical aggregate SHA256:
702ff847153f2436441b5816af85c0a3e5e40c56340e4688ce0a97a80c7b4d6f
Includes src/data/notebooks/results/reports, Event Automation, engine/models,
shared database/ingestion/scripts, all workflows and environment/ignore files.
All changed files are inside deployment/web. No Git commit or push.

## Limits and remaining deployment verification

- Visual/responsive browser QA is NOT verified. Computer Use stopped because it
  could not establish Brave's current URL confidently enough to enforce policy.
  No alternative browser automation was attempted. HTTP success/build validation
  is not a substitute for inspecting rendered charts, tooltips and mobile layouts.
- The isolated branch health response is truthfully DEGRADED: it contains no
  successful Market EOD execution log. Source data/inference itself is available.
  No log was fabricated or workflow changed to hide this condition.
- Freshness uses weekdays with a 21:30 IST settlement allowance, not a verified
  exchange-holiday calendar. The API explicitly states this limitation.
- Hosted deployment, hosting secrets, function timeout budgets, public production
  API behavior and remote rendering have not been verified. No production-ready
  claim or remote publication. Configure/verify hosting independently.
- Event Automation, EVENT_AUTOMATION_ENABLED and Market EOD configuration were
  left exactly as found. Production collection was not enabled.

Local preview: http://127.0.0.1:3210 (isolated database only).

## Exact created and modified files

- `deployment/web/IMPLEMENTATION_PLAN.md`
- `deployment/web/VERIFICATION.md`
- `deployment/web/app/api/v1/events/route.ts`
- `deployment/web/app/api/v1/health/route.ts`
- `deployment/web/app/api/v1/portfolios/route.ts`
- `deployment/web/app/api/v1/regime/history/route.ts`
- `deployment/web/app/api/v1/regime/latest/route.ts`
- `deployment/web/app/api/v1/rrg/route.ts`
- `deployment/web/app/economic-calendar/page.tsx`
- `deployment/web/app/event-intelligence/page.tsx`
- `deployment/web/app/globals.css`
- `deployment/web/app/layout.tsx`
- `deployment/web/app/page.tsx`
- `deployment/web/app/portfolio-analytics/page.tsx`
- `deployment/web/app/regime-intelligence/page.tsx`
- `deployment/web/app/research-methodology/page.tsx`
- `deployment/web/app/risk-drawdown/page.tsx`
- `deployment/web/app/sector-rotation/page.tsx`
- `deployment/web/components/analytics/chart.tsx`
- `deployment/web/components/analytics/controls.tsx`
- `deployment/web/components/ui/section-header.tsx`
- `deployment/web/components/ui/terminal-header.tsx`
- `deployment/web/components/ui/terminal-panel.tsx`
- `deployment/web/components/ui/top-navigation.tsx`
- `deployment/web/lib/analytics.ts`
- `deployment/web/lib/contracts.ts`
- `deployment/web/lib/freshness.ts`
- `deployment/web/lib/http.ts`
- `deployment/web/lib/neon.ts`
- `deployment/web/lib/research-artifacts.json`
- `deployment/web/lib/use-api.ts`
- `deployment/web/package.json`
- `deployment/web/tests/analytics.test.cjs`
- `deployment/web/tests/api.test.cjs`
- `deployment/web/tests/live-check.cjs`
- `deployment/web/tests/live-results.json`
- `deployment/web/tests/register.cjs`
