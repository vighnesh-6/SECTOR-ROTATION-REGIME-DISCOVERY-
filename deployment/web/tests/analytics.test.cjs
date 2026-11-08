require('./register.cjs');
const {test}=require('node:test'),assert=require('node:assert/strict');
const {performance,curve,baseNav}=require('../lib/analytics.ts');
const {numeric,validDate,severity,metadata,validInference}=require('../lib/contracts.ts');
const {expectedSession}=require('../lib/freshness.ts');
const close=(a,b,tol=1e-10)=>assert.ok(Math.abs(a-b)<tol,`${a} differs from ${b}`);
test('first selected return is included using actual previous NAV',()=>{
 const rows=[{date:'2025-01-02',net_nav:110,net_return:.1,previous_nav:100},{date:'2025-01-03',net_nav:99,net_return:-.1,previous_nav:110}];
 const p=performance(rows);close(p.total_return,-.01);close(p.max_drawdown,-.1);close(p.volatility,Math.sqrt(.02*252));close(p.sharpe,0);assert.equal(p.count,2);
 close(curve({test:rows})[0].test,110);close(curve({test:rows},true)[1].test,-10);
});
test('missing pre-window row derives baseline from observed first return',()=>{close(baseNav([{date:'2025-01-02',net_nav:99,net_return:-.01}]),100);});
test('undefined risk ratios and malformed series are not fabricated',()=>{
 const p=performance([{date:'2025-01-02',net_nav:1,net_return:0}]);assert.equal(p.volatility,null);assert.equal(p.sharpe,null);assert.equal(p.sortino,null);
 assert.equal(performance([]),null);assert.equal(performance([{date:'x',net_nav:'bad',net_return:0}]),null);assert.equal(numeric(null),null);assert.equal(numeric(''),null);assert.equal(numeric(false),null);
});
test('drawdown matches research observed-peak convention',()=>{const p=performance([{date:'1',net_nav:.9,net_return:-.1,previous_nav:1}]);close(p.total_return,-.1);close(p.max_drawdown,0);});
test('curves preserve missing dates rather than forward fill',()=>{const c=curve({A:[{date:'2025-01-01',net_nav:1,net_return:0}],B:[{date:'2025-01-02',net_nav:2,net_return:0}]});assert.equal(c[0].B,null);assert.equal(c[1].A,null);});
test('Sortino downside denominator includes all observations',()=>{const p=performance([{date:'1',net_nav:1.02,net_return:.02},{date:'2',net_nav:1.0098,net_return:-.01}]);close(p.sortino,.005*252/Math.sqrt(.0001/2*252));});
test('dates and event metadata are validated without default low/India',()=>{assert.ok(validDate('2024-02-29'));assert.ok(!validDate('2026-02-30'));assert.equal(severity(null),null);assert.equal(severity(42),null);assert.equal(severity('Severity: HIGH'),'high');assert.equal(severity('surprise'),null);assert.equal(metadata('Region: India / US','Region'),'India / US');});
test('freshness respects IST cutoff, weekend and UTC crossover',()=>{assert.equal(expectedSession(new Date('2026-11-08T05:00:00Z')),'2026-11-06');assert.equal(expectedSession(new Date('2026-11-09T14:00:00Z')),'2026-11-06');assert.equal(expectedSession(new Date('2026-11-09T16:30:00Z')),'2026-11-09');});
test('inference needs valid probability vector, IDs and confidence metadata',()=>{const r={accepted_regime:2,raw_argmax:2,max_probability:.8,is_confident:true,prob_0:.1,prob_1:.1,prob_2:.8,prob_3:0,prob_4:0,prob_5:0};assert.ok(validInference(r));assert.ok(!validInference({...r,prob_0:1}));assert.ok(!validInference({...r,accepted_regime:null}));assert.ok(!validInference({...r,is_confident:false}));assert.ok(!validInference({...r,raw_argmax:0}));});

test('missing numerical values use a proper unavailable marker',()=>{const {fmt,pct}=require('../lib/contracts.ts');assert.equal(fmt(null),String.fromCharCode(0x2014));assert.equal(pct(null),String.fromCharCode(0x2014));});
