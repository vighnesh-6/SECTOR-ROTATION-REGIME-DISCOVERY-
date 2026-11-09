// This module calls only allowlisted GitHub workflow/issue APIs. It cannot write
// market/event data. Existing workflow concurrency and append-only persistence
// make an ambiguous/repeated dispatch safe; this does not promise exactly-once HTTP.
export const REPOSITORY = 'vighnesh-6/SECTOR-ROTATION-REGIME-DISCOVERY-';
const BASE = `https://api.github.com/repos/${REPOSITORY}`;
const ALERT_MARKER = '<!-- sector-rotation-automation:v1 -->';
const TASKS = {
  eod: { file: 'daily_eod.yml', prefix: 'EOD', times: ['19:00','19:30','20:00','20:30'] },
  events: { file: 'daily_events.yml', prefix: 'Events', times: ['21:00'] },
  health: { file: 'daily_events.yml', prefix: 'Events', times: ['23:00'] },
};
const NAMES = {
  'eod-primary': ['eod','19:00'], 'eod-retry-1': ['eod','19:30'],
  'eod-retry-2': ['eod','20:00'], 'eod-retry-3': ['eod','20:30'],
  'events-primary': ['events','21:00'], 'events-health': ['health','23:00'],
  'eod-watchdog': ['eod',null], 'events-watchdog': ['events',null],
};

function localDay(value) {
  return new Intl.DateTimeFormat('en-CA', { timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit' }).format(value);
}
function dueAt(day, time) { return new Date(`${day}T${time}:00+05:30`); }

export async function tick({ name, scheduledAt, now = new Date(), token, fetcher = fetch }) {
  if (!token) throw new Error('AUTOMATION_GITHUB_TOKEN is not configured');
  if (!NAMES[name]) throw new Error('Unknown automation schedule');
  const planned = new Date(scheduledAt);
  if (!Number.isFinite(planned.getTime()) || !Number.isFinite(now.getTime())) throw new Error('Invalid scheduler clock');
  const day = localDay(planned);
  if ([0,6].includes(new Date(`${day}T12:00:00+05:30`).getUTCDay())) return { status:'SKIPPED',reason:'weekend',schedule:name };
  // Delayed delivery must never silently dispatch a different date.
  if (localDay(now) !== day) return { status:'SKIPPED',reason:'expired delivery; next weekday pipeline recovers its backlog',schedule:name };
  const [kind, fixed] = NAMES[name], task = TASKS[kind];
  const time = fixed ?? task.times.filter(t => dueAt(day,t) <= now).at(-1);
  if (!time || dueAt(day,time) > now) return { status:'SKIPPED',reason:'not due',schedule:name };
  const key = `ops:${kind}:${day}:${time.replace(':','')}`;
  const title = `${task.prefix} ${key}`;
  const outcome = { schedule:name, dispatch_key:key };
  async function api(path, method='GET', body) {
    let response;
    try {
      response = await fetcher(BASE+path, { method, redirect:'error',
        headers:{ Authorization:`Bearer ${token}`, Accept:'application/vnd.github+json',
          'X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json' },
        ...(body === undefined ? {} : { body:JSON.stringify(body) }), signal:AbortSignal.timeout(10000) });
    } catch {
      // A POST may have reached GitHub. Next watchdog checks its run key first.
      throw new Error('GitHub request outcome unconfirmed; next watchdog must inspect run history');
    }
    if (!response.ok) throw new Error(`GitHub automation request failed: HTTP ${response.status}`);
    if (response.status===204) return null;
    const text = await response.text();
    return text ? JSON.parse(text) : null;
  }
  let runs = [];
  for (let page=1;page<=3;page++) {
    const data = await api(`/actions/workflows/${task.file}/runs?created=${day}&per_page=100&page=${page}`);
    runs.push(...data.workflow_runs);
    if (data.workflow_runs.length < 100) break;
    if (page===3) throw new Error('Run history exceeds bounded scan; refusing an unverified duplicate dispatch');
  }
  // Exact keys distinguish external EOD, event collection and event health.
  const run = runs.filter(r => r.display_title===title && r.head_branch==='main')
    .sort((a,b) => b.id-a.id)[0];
  const alertTitle = `[Automation] ${kind} ${day}`;
  async function issue(reason, runUrl) {
    const issues = await api('/issues?state=open&per_page=100');
    const existing = issues.find(i => !i.pull_request && i.title===alertTitle && i.body?.includes(ALERT_MARKER));
    if (existing) return existing.number;
    const result = await api('/issues','POST',{ title:alertTitle,
      body:`${ALERT_MARKER}\nAutomated operational alert.\n\n${reason}\n\nSchedule: ${name}\nDispatch key: ${key}\n${runUrl ? `Workflow: ${runUrl}\n` : ''}\nExisting records must not be changed. Recovery is bounded to the guarded workflows.` });
    return result.number;
  }
  async function resolve() {
    const issues = await api('/issues?state=open&per_page=100');
    const existing = issues.find(i => !i.pull_request && i.title===alertTitle && i.body?.includes(ALERT_MARKER));
    // Only our deterministic operational title is touched, never unrelated issues.
    if (existing) await api(`/issues/${existing.number}`,'PATCH',{ state:'closed',state_reason:'completed' });
  }
  if (run?.status==='completed' && run.conclusion==='success') {
    await resolve();
    return { ...outcome,status:'SUCCESS',run_id:run.id,run_url:run.html_url };
  }
  if (run && run.status!=='completed') {
    const age = now-new Date(run.created_at);
    const alert = age>45*60000 ? await issue('Workflow is queued or running beyond the 45-minute allowance.',run.html_url) : null;
    return { ...outcome,status:'IN_PROGRESS',run_id:run.id,...(alert?{issue:alert}:{}) };
  }
  if (run) {
    const alert = await issue(`Workflow concluded ${run.conclusion}; recovery attempt ${run.run_attempt ?? 1}.`,run.html_url);
    if ((run.run_attempt ?? 1) >= 3) return { ...outcome,status:'FAILED',run_id:run.id,issue:alert,recovery:'bounded attempts exhausted' };
    if (now-new Date(run.updated_at)<15*60000) return { ...outcome,status:'RETRY_WAIT',run_id:run.id,issue:alert };
    await api(`/actions/runs/${run.id}/rerun-failed-jobs`,'POST',{});
    return { ...outcome,status:'RECOVERY_DISPATCHED',run_id:run.id,issue:alert };
  }
  const late = now-dueAt(day,time)>45*60000;
  const alert = late ? await issue('No matching workflow run exists after the scheduled allowance. Dispatching missed work.') : null;
  const inputs = { dispatch_key:key, trigger_origin:'external_scheduler',
    ...(kind==='eod' ? { target_date:day } : { mode:kind==='health'?'health':'live', days:'14' }) };
  await api(`/actions/workflows/${task.file}/dispatches`,'POST',{ ref:'main',inputs });
  return { ...outcome,status:late?'MISSED_RUN_RECOVERY_DISPATCHED':'DISPATCHED',...(alert?{issue:alert}:{}) };
}
