require('./register.cjs');
const {test}=require('node:test'),assert=require('node:assert/strict');
const {NextRequest}=require('next/server');
const neon=require('../lib/neon.ts'),realQuery=neon.queryNeon;
const req=url=>new NextRequest('http://localhost'+url);
const route=name=>require('../app/api/v1/'+name+'/route.ts');
test('portfolio rejects invalid variants, periods and impossible dates before querying',async()=>{
 neon.queryNeon=()=>{throw Error('must not query')};
 for(const suffix of ['?variant=300STOCKS','?period=constructor','?from_date=2026-02-30','?from_date=2026-11-08&to_date=2025-01-01']){
  const r=await route('portfolios').GET(req('/api/v1/portfolios'+suffix));assert.equal(r.status,400);
 }
});
test('portfolio queries provide pre-window baselines and latest return/turnover',async()=>{
 const calls=[];neon.queryNeon=async(sql,params)=>{calls.push({sql,params});return []};
 const r=await route('portfolios').GET(req('/api/v1/portfolios?period=holdout'));assert.equal(r.status,200);const d=await r.json();
 assert.equal(d.filters.from_date,'2025-01-02');assert.equal(d.filters.to_date,'2026-09-18');assert.match(calls[0].sql,/LAG\(net_nav\)/);assert.ok(!calls[0].sql.includes('SELECT *,date'));assert.match(calls[0].sql,/ORDER BY history.date/);assert.match(calls[2].sql,/net_return,actual_turnover/);
});
test('events enforce bounded integer pagination and parameterize limit/category',async()=>{
 let calls=[];neon.queryNeon=async(sql,params)=>{calls.push({sql,params});return sql.includes('AS total')?[{total:230}]:sql.startsWith('SELECT category')?[]:[{event_id:1,date:'2026-11-06',actual:null,forecast:null,previous:null}]};
 for(const suffix of ['?limit=0','?limit=NaN','?limit=10;DROP TABLE macro_events','?offset=-1'])assert.equal((await route('events').GET(req('/api/v1/events'+suffix))).status,400);
 const r=await route('events').GET(req('/api/v1/events?limit=50&category=Monetary%20policy'));const d=await r.json();assert.equal(d.total,230);assert.equal(d.events[0].severity,null);assert.equal(d.events[0].region,null);assert.ok(calls[0].sql.includes('LIMIT $4 OFFSET $5'));assert.deepEqual(calls[0].params.slice(-2),[50,0]);
});
test('latest regime fails honestly when missing or invalid; never defaults R0',async()=>{
 neon.queryNeon=async()=>[];assert.equal((await route('regime/latest').GET()).status,404);
 neon.queryNeon=async()=>[{accepted_regime:0}];assert.equal((await route('regime/latest').GET()).status,503);
});
test('regime history exposes invalid observations as gaps',async()=>{
 neon.queryNeon=async()=>[{date:'2026-11-06',accepted_regime:null}];
 const d=await (await route('regime/history').GET(req('/api/v1/regime/history'))).json();assert.equal(d.invalid_rows,1);assert.equal(d.history[0].R0,null);assert.equal(d.history[0].accepted_regime,null);
});
test('health is degraded for empty/stale data and ignores event execution logs',async()=>{
 let calls=[];neon.queryNeon=async sql=>{calls.push(sql);return []};
 const d=await (await route('health').GET()).json();assert.equal(d.status,'DEGRADED');assert.equal(d.indices.length,8);assert.ok(d.reasons.length>0);assert.ok(calls.some(s=>s.includes("trigger_type <> 'event_collector'")));
});
test('every API sanitizes upstream exceptions without credentials',async()=>{
 neon.queryNeon=async()=>{throw Error('postgresql://user:DO-NOT-EXPOSE@host/db')};
 for(const [name,path] of [['portfolios','/api/v1/portfolios'],['events','/api/v1/events'],['rrg','/api/v1/rrg'],['regime/latest',null],['regime/history','/api/v1/regime/history'],['health',null]]){
  const r=await route(name).GET(path?req(path):undefined);assert.equal(r.status,503);assert.ok(!(await r.text()).includes('DO-NOT-EXPOSE'));
 }
});
test('RRG validates trail and returns finite trails from aligned observed prices',async()=>{
 neon.queryNeon=async()=>{const rows=[];for(let i=0;i<80;i++)for(const [j,s] of ['NIFTY 50','NIFTY AUTO','NIFTY BANK','NIFTY FMCG','NIFTY IT','NIFTY METAL','NIFTY PHARMA'].entries())rows.push({date:new Date(Date.UTC(2026,0,i+1)).toISOString().slice(0,10),symbol:s,close:100+i*(j+1)+Math.sin(i)*(j+1)});return rows;};
 assert.equal((await route('rrg').GET(req('/api/v1/rrg?trail=-1'))).status,400);
 const d=await (await route('rrg').GET(req('/api/v1/rrg?trail=5'))).json();assert.equal(Object.keys(d.sectors).length,6);
 for(const s of Object.values(d.sectors)){assert.equal(s.trail.length,5);assert.ok(s.trail.every(t=>Number.isFinite(t.rs_ratio)&&Number.isFinite(t.rs_momentum)));}
});
test('website client cannot accidentally select EVENT_TEST_DATABASE_URL as production',()=>{
 const fs=require('node:fs'),saved=fs.readFileSync,env={DATABASE_URL:process.env.DATABASE_URL,NEON_DATABASE_URL:process.env.NEON_DATABASE_URL};
 delete process.env.DATABASE_URL;delete process.env.NEON_DATABASE_URL;
 try{fs.readFileSync=()=> 'EVENT_TEST_DATABASE_URL=postgresql://test:secret@isolated/db\nNEON_DATABASE_URL=postgresql://website:secret@configured/db\n';assert.equal(neon.getConnectionString(),'postgresql://website:secret@configured/db');}
 finally{fs.readFileSync=saved;for(const [k,v]of Object.entries(env)){if(v===undefined)delete process.env[k];else process.env[k]=v;}}
});
test('website database transport is SELECT-only and never leaks error bodies',async()=>{
 const saved=global.fetch,connection=process.env.DATABASE_URL;process.env.DATABASE_URL='postgresql://test:secret@isolated.neon.tech/db';
 try{
  await assert.rejects(()=>realQuery('DELETE FROM macro_events'),/read-only/);
  global.fetch=async()=>({ok:false,status:500,text:async()=>'DO-NOT-EXPOSE'});await assert.rejects(()=>realQuery('SELECT 1'),e=>!e.message.includes('DO-NOT-EXPOSE'));
 }finally{global.fetch=saved;if(connection===undefined)delete process.env.DATABASE_URL;else process.env.DATABASE_URL=connection;}
});

test('read-only transport retries transient failures but not SQL rejection',async()=>{
 const saved=global.fetch,connection=process.env.DATABASE_URL;process.env.DATABASE_URL='postgresql://test:secret@isolated.neon.tech/db';
 try {
  let count=0;global.fetch=async()=>{count++;if(count===1)throw Error('network reset');return {ok:true,json:async()=>({rows:[{connected:1}]})};};
  assert.deepEqual(await realQuery('SELECT 1'),[{connected:1}]);assert.equal(count,2);
  count=0;global.fetch=async()=>{count++;return {ok:false,status:400};};await assert.rejects(()=>realQuery('SELECT 1'),/request failed/);assert.equal(count,1);
 }finally{global.fetch=saved;if(connection===undefined)delete process.env.DATABASE_URL;else process.env.DATABASE_URL=connection;}
});
