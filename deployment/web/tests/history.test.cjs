require('./register.cjs');
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { NextRequest } = require('next/server');
const neon = require('../lib/neon.ts');
const { individualNavHistory, regimeLabel, regimeStatus, decisionStatus, executionStatus } = require('../lib/history.ts');
const { chartSeries, SERIES_COLORS } = require('../lib/chart-series.ts');
const request = query => new NextRequest('http://localhost/api/v1/portfolios/history' + query);
const api = require('../app/api/v1/portfolios/history/route.ts');

test('individual NAV remains in stored units, sorted by date, without filling missing variants', () => {
  const rows = [
    { date: '2026-11-06', variant: '1A', net_nav: '5.123456' },
    { date: '2026-11-05', variant: '1B', net_nav: '4.987654' },
    { date: '2026-11-06', variant: '2B', net_nav: null },
  ];
  const result = individualNavHistory(rows);
  assert.equal(result[0].date, '2026-11-05');
  assert.equal(result[0]['1A'], null);
  assert.equal(result[0]['1B'], 4.987654);
  assert.equal(result[1]['1A'], 5.123456);
  assert.equal(result[1]['1B'], null);
  assert.equal(result[1]['2B'], null);
  assert.deepEqual(individualNavHistory([]), []);
});

test('acceptance status uses stored flags and never treats acceptance as execution', () => {
  assert.equal(regimeLabel(0), 'R0');
  assert.equal(regimeLabel(null), 'Unavailable');
  assert.equal(regimeLabel(9), 'Unavailable');
  assert.equal(regimeStatus({ raw_argmax: 1, accepted_regime: 2, is_confident: false }), 'Incumbent retained - low confidence');
  assert.equal(regimeStatus({ raw_argmax: 1, accepted_regime: 1, is_confident: true }), 'Raw candidate accepted');
  assert.equal(regimeStatus({ raw_argmax: 1, accepted_regime: 2, is_confident: true }), 'Stored accepted state differs from raw');
  assert.match(regimeStatus({ raw_argmax: 1, accepted_regime: 1, is_confident: null }), /Unavailable/);
  assert.match(regimeStatus({ raw_argmax: 9, accepted_regime: 9, is_confident: true }), /Unavailable/);
  assert.equal(decisionStatus(true), 'Rebalance triggered');
  assert.equal(decisionStatus(false), 'No rebalance triggered');
  assert.equal(decisionStatus(null), 'Decision unavailable');
});

test('execution requires an actual stored simulation flag, not a scheduled date or decision', () => {
  assert.equal(executionStatus({ rebalance_triggered: true, scheduled_execution_date: '2026-11-09' }), 'No execution record');
  assert.equal(executionStatus({ execution_record_date: '2026-11-06', execution_rebalance_executed: false, execution_actual_turnover: 0 }), 'Not executed (simulation)');
  assert.equal(executionStatus({ execution_record_date: '2026-11-06', execution_rebalance_executed: true }), 'Executed (simulation)');
  assert.equal(executionStatus({ execution_record_date: '2026-11-06', execution_rebalance_executed: null }), 'Execution flag unavailable');
});

test('series identities have consistent colors and readable benchmark/regime labels', () => {
  for (const key of ['1A','1B','2A','2B','AUTO','BANK','FMCG','IT','METAL','PHARMA','CASH','R0','R1','R2','R3','R4','R5','NIFTY50_BUY_HOLD','EQUAL_WEIGHT_6SECTOR']) {
    assert.ok(SERIES_COLORS[key]);
    assert.equal(chartSeries(key).color, SERIES_COLORS[key]);
    assert.ok(!chartSeries(key).label.includes('_'));
  }
  assert.match(chartSeries('EQUAL_WEIGHT_6SECTOR').label, /Six-sector/);
});

test('portfolio history rejects invalid session counts and date ranges before database access', async () => {
  neon.queryNeon = () => { throw new Error('must not query'); };
  for (const query of ['?recent_sessions=9', '?recent_sessions=16', '?recent_sessions=NaN', '?from_date=2026-02-30', '?from_date=2026-11-08&to_date=2026-01-01']) {
    assert.equal((await api.GET(request(query))).status, 400);
  }
});

test('history API preserves raw NAV and execution absence, and defines cumulative scopes', async () => {
  const calls = [];
  const recent = [{ date: '2026-11-06', variant: '1A', net_nav: '5.123456' }];
  const turnover = [{ date: '2026-11-06', variant: '1A', actual_turnover: '0.000000', cumulative_selected_period: '0.500000', cumulative_all_history: '12.500000' }];
  const decisions = [{ variant: '1A', signal_date: '2026-11-06', scheduled_execution_date: '2026-11-09', rebalance_triggered: true, execution_record_date: null, actual_execution_date: null, execution_actual_turnover: null }];
  neon.queryNeon = async (sql, params) => {
    calls.push({ sql, params });
    return sql.includes('recent_dates') ? recent : sql.includes('entire_history') ? turnover : decisions;
  };
  const response = await api.GET(request('?recent_sessions=10&from_date=2026-11-01&to_date=2026-11-06'));
  const data = await response.json();
  assert.equal(response.status, 200);
  assert.deepEqual(data.recent_nav, recent);
  assert.deepEqual(data.turnover_history, turnover);
  assert.deepEqual(data.rebalance_history, decisions);
  assert.equal(data.recent_sessions_requested, 10);
  assert.equal(data.recent_sessions_returned, 1);
  assert.deepEqual(calls[0].params, [10]);
  assert.deepEqual(calls[1].params, ['2026-11-01', '2026-11-06']);
  assert.match(data.scopes.cumulative_selected_period, /selected start/);
  assert.match(data.scopes.cumulative_all_history, /first stored simulation/);
  assert.ok(calls[1].sql.indexOf('SUM(actual_turnover) OVER running') < calls[1].sql.indexOf('WHERE date'));
  assert.match(calls[1].sql, /COUNT\(\*\).*COUNT\(actual_turnover\)/);
  assert.match(calls[2].sql, /e.variant = a.variant AND e.date = a.exec_date/);
  assert.match(calls[2].sql, /CASE WHEN e.rebalance_executed THEN e.date::text END/);
  assert.ok(calls.every(c => !/\b(INSERT|UPDATE|DELETE|ALTER|CREATE|DROP)\b/i.test(c.sql)));
});

test('historical regime API exposes stored raw candidate, accepted probability and confidence', async () => {
  const source = { date: '2026-11-06', period: 'catchup', raw_argmax: 0, accepted_regime: 2, is_confident: false, max_probability: '.4', prob_0: '.4', prob_1: '.1', prob_2: '.2', prob_3: '.1', prob_4: '.1', prob_5: '.1' };
  neon.queryNeon = async () => [source];
  const handler = require('../app/api/v1/regime/history/route.ts');
  const response = await handler.GET(new NextRequest('http://localhost/api/v1/regime/history'));
  const data = await response.json();
  assert.equal(data.history[0].raw_argmax, 0);
  assert.equal(data.history[0].accepted_regime, 2);
  assert.equal(data.history[0].is_confident, false);
  assert.equal(data.history[0].max_probability, .4);
  assert.equal(data.history[0].accepted_probability, .2);
  assert.equal(data.history[0].R0, .4);
});

test('invalid regime history does not substitute candidate IDs or confidence', async () => {
  neon.queryNeon = async () => [{ date: '2026-11-06', raw_argmax: null, accepted_regime: null }];
  const handler = require('../app/api/v1/regime/history/route.ts');
  const data = await (await handler.GET(new NextRequest('http://localhost/api/v1/regime/history'))).json();
  for (const key of ['raw_argmax','accepted_regime','max_probability','accepted_probability','is_confident','R0']) assert.equal(data.history[0][key], null);
  assert.equal(data.invalid_rows, 1);
});

test('history service failure never exposes upstream credentials', async () => {
  neon.queryNeon = async () => { throw new Error('postgresql://owner:NEVER-EXPOSE@host/db'); };
  const response = await api.GET(request(''));
  assert.equal(response.status, 503);
  assert.ok(!(await response.text()).includes('NEVER-EXPOSE'));
});

// Inspect the actual chart element/tooltip contracts without a browser or generated data.
test('shared chart renders readable legends, correct units and date/value tooltips without filling gaps', () => {
  const fs = require('node:fs'), ts = require('typescript');
  require.extensions['.tsx'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true }
  }).outputText, filename);
  const { renderToStaticMarkup } = require('react-dom/server');
  const { ResearchChart } = require('../components/analytics/chart.tsx');
  const recharts = require('recharts');
  const observation = { date: '2026-11-06', '1A': 5.123456, '1B': null };
  const tree = ResearchChart({ data: [observation], keys: ['1A','1B'], label: 'Stored Net NAV', yLabel: 'Net NAV (stored units)', decimals: 4, tooltipDecimals: 6, points: true });
  const nodes = [];
  function visit(value) { if (Array.isArray(value)) return value.forEach(visit); if (!value?.props) return; nodes.push(value); visit(value.props.children); }
  visit(tree);
  const legend = renderToStaticMarkup(nodes.find(node => node.type === 'ul'));
  assert.match(legend, /1A - Template A/); assert.match(legend, /1B - Template A/);
  assert.equal(nodes.find(node => node.type === recharts.YAxis).props.label.value, 'Net NAV (stored units)');
  assert.equal(nodes.find(node => node.type === recharts.XAxis).props.label.value, 'Trading session');
  for (const line of nodes.filter(node => node.type === recharts.Line)) assert.equal(line.props.connectNulls, false);
  const tooltip = nodes.find(node => node.type === recharts.Tooltip).props.content;
  const html = renderToStaticMarkup(tooltip({ active: true, payload: [{ payload: observation }], label: observation.date }));
  assert.match(html, /2026-11-06/); assert.match(html, /5\.123456/); assert.match(html, /Unavailable/);
  assert.match(html, /Net NAV \(stored units\)/);
});
