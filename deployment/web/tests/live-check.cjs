/** Read-only HTTP integration checks. Start the website with the isolated test URL first. */
require('./register.cjs');
const assert=require('node:assert/strict');
const {performance}=require('../lib/analytics.ts');
const {validInference}=require('../lib/contracts.ts');
const frozen=require('../lib/research-artifacts.json');
const base=process.env.WEBSITE_TEST_BASE_URL||'http://127.0.0.1:3210';
assert.ok(/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base),'Only an explicit local preview is accepted.');
const report={base,routes:[],apis:[],metric_comparisons:[],notes:[]};
async function get(path,expected=200){
 const response=await fetch(base+path,{signal:AbortSignal.timeout(45000)}),text=await response.text();
 assert.equal(response.status,expected,`${path}: HTTP ${response.status}`);
 if(path.startsWith('/api')){report.apis.push({path,status:response.status});return JSON.parse(text);}
 assert.ok(!text.includes('Application error'));report.routes.push({path,status:response.status});return text;
}
(async()=>{
 for(const path of ['/','/sector-rotation','/portfolio-analytics','/risk-drawdown','/economic-calendar','/event-intelligence','/regime-intelligence','/research-methodology'])await get(path);
 const h=await get('/api/v1/health');assert.equal(h.database.connected,true);assert.equal(h.indices.length,8);assert.equal(h.inference.valid,true);report.notes.push({health:h.status,reasons:h.reasons});
 const r=await get('/api/v1/regime/latest');assert.equal(r.probabilities.length,6);assert.ok(Math.abs(r.probabilities.reduce((a,p)=>a+p.prob,0)-1)<1e-5);assert.equal(r.current_allocations.length,4);
 const history=await get('/api/v1/regime/history?from_date=2025-01-02&to_date=2026-09-18');assert.equal(history.invalid_rows,0);assert.equal(history.history.length,422);
 const graph=await get('/api/v1/rrg?trail=5');assert.equal(Object.keys(graph.sectors).length,6);
 for(const s of Object.values(graph.sectors)){assert.equal(s.trail.length,5);assert.ok(s.trail.every(p=>Number.isFinite(p.rs_ratio)&&Number.isFinite(p.rs_momentum)));}
 const page1=await get('/api/v1/events?limit=50'),page2=await get('/api/v1/events?limit=50&offset=50');assert.equal(page1.total,230);assert.equal(page1.count,50);assert.equal(page2.count,50);assert.ok(!page1.events.some(a=>page2.events.some(b=>a.event_id===b.event_id)));
 for(const category of page1.categories){const d=await get('/api/v1/events?limit=1&category='+encodeURIComponent(category.category));assert.ok(d.events.every(e=>e.category===category.category));}
 for(const period of ['train','holdout','post','full']){
  const d=await get('/api/v1/portfolios?period='+period);
  for(const variant of ['1A','1B','2A','2B']){
   const rows=d.strategy_simulations.filter(r=>r.variant===variant),m=performance(rows);
   assert.ok(m&&m.count>0,`${period} ${variant}: missing performance`);
   const holding=d.latest_holdings.find(r=>r.variant===variant);assert.ok(holding);assert.notEqual(holding.net_return,undefined);assert.notEqual(holding.actual_turnover,undefined);
   assert.ok(rows.every(r=>Number.isFinite(Number(r.previous_nav))||r.previous_nav===null));
   if(['train','holdout'].includes(period)){
    const reference=frozen.strategy_metrics.find(r=>r.variant===variant&&r.period===period);assert.equal(m.count,reference.return_intervals);
    for(const [key,col,div] of [['total_return','total_return_net_pct',100],['cagr','cagr_net_pct',100],['volatility','ann_volatility_pct',100],['sharpe','sharpe_ratio',1],['sortino','sortino_ratio',1],['max_drawdown','max_drawdown_pct',100]]){
     const diff=Math.abs(m[key]-reference[col]/div);assert.ok(diff<1e-5,`${period} ${variant} ${key} differs from frozen research by ${diff}`);
    }
    report.metric_comparisons.push({variant,period,intervals:m.count,six_metrics:'MATCH within 1e-5 absolute tolerance'});
   }
  }
  assert.equal(new Set(d.benchmark_simulations.map(r=>r.benchmark_name)).size,2);
 }
 for(const [path,status] of [['/api/v1/portfolios?variant=INVALID',400],['/api/v1/events?limit=NaN',400],['/api/v1/rrg?trail=0',400],['/api/v1/regime/history?from_date=2026-02-30',400]])await get(path,status);
 console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error(e.message);process.exitCode=1;});
