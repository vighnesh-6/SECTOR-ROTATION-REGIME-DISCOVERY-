import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { tick,REPOSITORY } from '../lib/dispatcher.mjs';

const marker='<!-- sector-rotation-automation:v1 -->';
const at = t => new Date(`2026-11-09T${t}:00+05:30`);
const run = overrides => ({ id:123,head_branch:'main',display_title:'EOD ops:eod:2026-11-09:1900',
  status:'completed',conclusion:'success',run_attempt:1,
  created_at:at('19:00').toISOString(),updated_at:at('19:10').toISOString(),
  html_url:`https://github.com/${REPOSITORY}/actions/runs/123`,...overrides });

function mock({runs=[],issues=[],status,ambiguous=false,fullPages=false}={}) {
  const calls=[];
  const fetcher=async (url,options) => {
    assert.ok(url.startsWith(`https://api.github.com/repos/${REPOSITORY}/`));
    assert.equal(options.redirect,'error');
    const body=options.body ? JSON.parse(options.body) : undefined;
    calls.push({url,method:options.method,body});
    if (status) return new Response('upstream secret must not escape',{status});
    if (url.includes('/actions/workflows/') && options.method==='GET') return Response.json({workflow_runs:fullPages?Array(100).fill(run()):runs});
    if (url.includes('/issues?')) return Response.json(issues);
    if (url.endsWith('/dispatches')) {
      if (ambiguous) throw new Error('private credential');
      return new Response(null,{status:204});
    }
    if (url.endsWith('/rerun-failed-jobs')) return new Response(null,{status:201});
    if (url.endsWith('/issues')) return Response.json({number:31},{status:201});
    if (/\/issues\/\d+$/.test(url) && options.method==='PATCH') return Response.json({state:'closed'});
    throw new Error('Unexpected test URL');
  };
  return {calls,fetcher};
}
function invoke(m, args={}) {
  return tick({name:'eod-primary',scheduledAt:at('19:00'),now:at('19:05'),token:'offline-secret',fetcher:m.fetcher,...args});
}

test('EOD dispatch has fixed repository, main branch, exact session and correlation key',async()=>{
  const m=mock();const r=await invoke(m);
  assert.equal(r.status,'DISPATCHED');
  const c=m.calls.find(c=>c.url.endsWith('/dispatches'));
  assert.ok(c.url.includes('/daily_eod.yml/'));
  assert.deepEqual(c.body,{ref:'main',inputs:{dispatch_key:'ops:eod:2026-11-09:1900',trigger_origin:'external_scheduler',target_date:'2026-11-09'}});
});
test('Event collection and health remain distinct operations',async()=>{
  for (const [name,time,mode] of [['events-primary','21:00','live'],['events-health','23:00','health']]) {
    const m=mock();await invoke(m,{name,scheduledAt:at(time),now:at(time)});
    const c=m.calls.find(c=>c.url.endsWith('/dispatches'));
    assert.ok(c.url.includes('daily_events.yml'));
    assert.equal(c.body.inputs.mode,mode);
    assert.equal(c.body.inputs.days,'14');
  }
});
test('Missing credential, unknown schedule and invalid clocks fail before any request',async()=>{
  for (const extra of [{token:''},{name:'untrusted'},{scheduledAt:'invalid'}]) {
    const m=mock();await assert.rejects(invoke(m,extra));assert.equal(m.calls.length,0);
  }
});
test('Weekend, early and old-date deliveries cannot dispatch work',async()=>{
  for (const extra of [
    {scheduledAt:new Date('2026-11-08T19:00:00+05:30'),now:new Date('2026-11-08T19:05:00+05:30')},
    {now:at('18:59')}, {now:new Date('2026-11-10T19:00:00+05:30')},
  ]) {const m=mock();assert.equal((await invoke(m,extra)).status,'SKIPPED');assert.equal(m.calls.length,0);}
});
test('A repeated successful key is observed without another dispatch',async()=>{
  const m=mock({runs:[run()]});assert.equal((await invoke(m)).status,'SUCCESS');
  assert.equal(m.calls.filter(c=>c.method!=='GET').length,0);
});
test('A queued/running key is not dispatched again',async()=>{
  const m=mock({runs:[run({status:'in_progress',conclusion:null})]});
  assert.equal((await invoke(m)).status,'IN_PROGRESS');
  assert.equal(m.calls.filter(c=>c.method!=='GET').length,0);
});
test('A missed-run watchdog dispatches the latest due recovery slot',async()=>{
  const m=mock();const r=await invoke(m,{name:'eod-watchdog',scheduledAt:at('21:30'),now:at('21:35')});
  assert.equal(r.status,'MISSED_RUN_RECOVERY_DISPATCHED');
  assert.equal(r.dispatch_key,'ops:eod:2026-11-09:2030');assert.equal(r.issue,31);
  assert.equal(m.calls.filter(c=>c.url.endsWith('/dispatches')).length,1);
});
test('Failed workflow recovery is bounded to three attempts and waits 15 minutes',async()=>{
  for (const [extra,now,expected] of [
    [{conclusion:'failure'},'19:30','RECOVERY_DISPATCHED'],
    [{conclusion:'failure'},'19:15','RETRY_WAIT'],
    [{conclusion:'failure',run_attempt:3},'19:30','FAILED'],
  ]) {
    const m=mock({runs:[run(extra)]});const r=await invoke(m,{now:at(now)});
    assert.equal(r.status,expected);
    assert.equal(m.calls.filter(c=>c.url.endsWith('/rerun-failed-jobs')).length,expected==='RECOVERY_DISPATCHED'?1:0);
    assert.equal(m.calls.filter(c=>c.url.endsWith('/dispatches')).length,0);
  }
});
test('Failure alerts are deduplicated and only owned alerts can be resolved',async()=>{
  const owned={number:31,title:'[Automation] eod 2026-11-09',body:marker};
  const m=mock({runs:[run({conclusion:'failure',run_attempt:3})],issues:[owned]});
  assert.equal((await invoke(m)).issue,31);
  assert.equal(m.calls.filter(c=>c.url.endsWith('/issues')&&c.method==='POST').length,0);
  for (const body of [marker,'unrelated user issue']) {
    const n=mock({runs:[run()],issues:[{...owned,body}]});await invoke(n);
    assert.equal(n.calls.filter(c=>c.method==='PATCH').length,body===marker?1:0);
  }
});
test('No immediate POST replay after an ambiguous dispatch; next observation suppresses duplicate',async()=>{
  const m=mock({ambiguous:true});await assert.rejects(invoke(m),/unconfirmed/);
  assert.equal(m.calls.filter(c=>c.url.endsWith('/dispatches')).length,1);
  const n=mock({runs:[run({status:'queued',conclusion:null})]});
  assert.equal((await invoke(n)).status,'IN_PROGRESS');
  assert.equal(n.calls.filter(c=>c.method==='POST').length,0);
});
test('HTTP failures never expose upstream body or credentials',async()=>{
  for (const status of [401,403,429,500]) {
    await assert.rejects(invoke(mock({status})),e=>e.message.includes(`HTTP ${status}`)&&!e.message.includes('secret'));
  }
});
test('History overflow fails closed, and runs from another branch cannot mask missing work',async()=>{
  const m=mock({fullPages:true});await assert.rejects(invoke(m),/bounded scan/);
  assert.equal(m.calls.filter(c=>c.method==='POST').length,0);
  const n=mock({runs:[run({head_branch:'other'})]});assert.equal((await invoke(n)).status,'DISPATCHED');
});
test('Private independent schedules preserve the nominal times and stay inside Hobby quota',async()=>{
  const config=JSON.parse(await readFile(new URL('../vercel.json',import.meta.url),'utf8'));
  assert.equal(config.functions['api/dispatch.mjs'].experimentalTriggers[0].type,'schedule/v1beta');
  assert.equal(config.schedules['eod-primary'].schedule,'0 19 * * 1-5');
  assert.equal(config.schedules['events-primary'].schedule,'0 21 * * 1-5');
  assert.equal(config.schedules['events-health'].schedule,'0 23 * * 1-5');
  assert.equal(Object.keys(config.schedules).length,8);
  assert.ok((20+12+6)*23<5000);
  for (const s of Object.values(config.schedules)) {assert.equal(s.timezone,'Asia/Kolkata');assert.equal(s.jitter,15);assert.equal(s.function,'api/dispatch');}
});
