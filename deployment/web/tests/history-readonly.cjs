/** Opt-in SELECT-only checks. Requires the confirmed isolated connection in process memory. */
require('./register.cjs');
const assert = require('node:assert/strict');
const { NextRequest } = require('next/server');
const connection = process.env.EVENT_TEST_DATABASE_URL;
assert.ok(connection, 'EVENT_TEST_DATABASE_URL is required; no production fallback.');
const url = new URL(connection);
assert.equal(url.hostname.replace('-pooler.', '.'), 'ep-cold-wind-a14dq44q.ap-southeast-1.aws.neon.tech');
process.env.DATABASE_URL = connection;
process.env.NEON_DATABASE_URL = connection;
const { queryNeon } = require('../lib/neon.ts');
const portfolios = require('../app/api/v1/portfolios/history/route.ts');
const regimes = require('../app/api/v1/regime/history/route.ts');
const near = (a, b) => assert.ok(Math.abs(Number(a)-Number(b)) < 1e-8, 'Stored cumulative turnover mismatch');
async function get(handler, path) {
  const response = await handler.GET(new NextRequest('http://localhost' + path));
  assert.equal(response.status, 200, await response.clone().text());
  return response.json();
}
const tables = ['index_candles_daily','market_features_daily','regime_inference_daily','portfolio_allocations_daily','portfolio_simulations_daily','benchmark_simulations_daily','macro_events','pipeline_execution_logs','reconciliation_audit_logs'];
async function snapshot() {
  const rows = {};
  for (const table of tables) rows[table] = (await queryNeon("SELECT COUNT(*)::int AS rows,md5(COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text,'[]')) AS digest FROM " + table + ' t'))[0];
  return rows;
}
(async () => {
  const identity = (await queryNeon("SELECT current_setting('neon.branch_id',true) AS branch_id"))[0];
  assert.equal(identity.branch_id, 'br-odd-star-a1hjl6dl');
  const before = await snapshot();
  let details;
  try {
    const fifteen = await get(portfolios, '/api/v1/portfolios/history?recent_sessions=15&from_date=2026-10-16&to_date=2026-11-06');
    const ten = await get(portfolios, '/api/v1/portfolios/history?recent_sessions=10&from_date=2026-10-16&to_date=2026-11-06');
    assert.equal(fifteen.recent_sessions_returned, 15);
    assert.equal(ten.recent_sessions_returned, 10);
    for (const v of ['1A','1B','2A','2B']) {
      assert.equal(fifteen.recent_nav.filter(r=>r.variant===v).length, 15);
      assert.equal(ten.recent_nav.filter(r=>r.variant===v).length, 10);
    }
    const storedNav = await queryNeon('SELECT variant,date::text AS date,net_nav FROM portfolio_simulations_daily ORDER BY date DESC,variant LIMIT 60');
    const navMap = new Map(storedNav.map(r=>[r.variant+r.date,r.net_nav]));
    for (const r of fifteen.recent_nav) assert.equal(r.net_nav, navMap.get(r.variant+r.date));
    const window = await get(portfolios, '/api/v1/portfolios/history?from_date=2025-01-02&to_date=2026-09-18');
    const sums = await queryNeon("SELECT variant,SUM(actual_turnover) AS all_history,SUM(actual_turnover) FILTER(WHERE date >= '2025-01-02'::date) AS selected FROM portfolio_simulations_daily WHERE date <= '2026-09-18'::date GROUP BY variant");
    for (const sum of sums) {
      const rows = window.turnover_history.filter(r=>r.variant===sum.variant),last=rows.at(-1);
      assert.equal(rows.length,422);
      near(rows[0].cumulative_selected_period, rows[0].actual_turnover);
      near(last.cumulative_selected_period, sum.selected);
      near(last.cumulative_all_history, sum.all_history);
      assert.ok(Number(last.cumulative_all_history)>Number(last.cumulative_selected_period));
    }
    const executions = await queryNeon("SELECT variant,date::text AS date,rebalance_executed,actual_turnover FROM portfolio_simulations_daily WHERE date >= '2025-01-02'::date");
    const executionMap = new Map(executions.map(r=>[r.variant+r.date,r]));
    let recorded = 0, missing = 0, executed = 0;
    for (const row of [...window.rebalance_history,...fifteen.rebalance_history]) {
      const stored = executionMap.get(row.variant+row.scheduled_execution_date);
      if (!stored) {
        missing++;
        assert.equal(row.execution_record_date,null);
        assert.equal(row.execution_rebalance_executed,null);
        assert.equal(row.actual_execution_date,null);
        assert.equal(row.execution_actual_turnover,null);
      } else {
        recorded++;
        assert.equal(row.execution_rebalance_executed,stored.rebalance_executed);
        assert.equal(row.execution_record_date,stored.date);
        near(row.execution_actual_turnover,stored.actual_turnover);
        assert.equal(row.actual_execution_date,stored.rebalance_executed?stored.date:null);
        if (stored.rebalance_executed) executed++;
      }
    }
    assert.ok(missing>0); assert.ok(executed>0);
    const history = await get(regimes,'/api/v1/regime/history?from_date=2026-10-16&to_date=2026-11-06');
    const stored = await queryNeon("SELECT date::text AS date,raw_argmax,accepted_regime,max_probability,is_confident,prob_0,prob_1,prob_2,prob_3,prob_4,prob_5 FROM regime_inference_daily WHERE date BETWEEN '2026-10-16'::date AND '2026-11-06'::date ORDER BY date");
    assert.equal(history.history.length,15);
    assert.equal(history.invalid_rows,0);
    for (let i=0;i<stored.length;i++){
      const actual=history.history[i],source=stored[i];
      assert.equal(actual.raw_argmax,source.raw_argmax);
      assert.equal(actual.accepted_regime,source.accepted_regime);
      assert.equal(actual.is_confident,source.is_confident);
      near(actual.max_probability,source.max_probability);
      near(actual.accepted_probability,source['prob_'+source.accepted_regime]);
    }
    details = { branch: identity.branch_id, recent_nav_rows_15: fifteen.recent_nav.length, recent_nav_rows_10: ten.recent_nav.length,
      scope_checks: 'all four variants match independent SELECT SUMs; first-window return not involved',
      execution_records_checked: recorded, executions_with_true_stored_flag: executed, absent_execution_records_preserved: missing,
      regime_rows_checked: history.history.length };
  } finally {
    const after = await snapshot();
    assert.deepEqual(after,before,'Database table contents changed during read-only verification');
    console.log(JSON.stringify({ database_fingerprints_unchanged:tables.length, macro_events_preserved:before.macro_events.rows }));
  }
  console.log(JSON.stringify(details));
})().catch(error => { console.error(error.message); process.exitCode=1; });
