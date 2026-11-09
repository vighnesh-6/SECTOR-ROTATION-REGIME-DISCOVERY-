# Independent production automation

This is a separate Vercel project (`sector-rotation-automation`) in the existing
`ayess` Hobby account. Its root is `deployment/automation`. The website remains
in `deployment/web`; no website code or database connection belongs here.

## Configuration and security

Configure Sensitive Production `AUTOMATION_GITHUB_TOKEN`: a fine-grained GitHub
token restricted to `vighnesh-6/SECTOR-ROTATION-REGIME-DISCOVERY-`, with Actions
read/write, Issues read/write, and implicit Metadata read. Never use the broad
local Git Credential Manager login as this runtime credential. Set
`AUTOMATION_ENABLED=true` only after the dedicated credential is configured.
Record its expiration and arrange rotation before expiry; GitHub App
installation authentication is an alternative if token maintenance is unwanted.

Do not configure `DATABASE_URL`, Neon credentials, or website environment files.
The private `schedule/v1beta` function has no public trigger URL. It dispatches
only the two fixed workflow files on `main`. It cannot change GitHub secrets or
directly query/write Neon. Those workflows retain their child-identity checks,
independent concurrency groups and append-only persistence.

## Timing, limits and recovery

Nominal weekday times in Asia/Kolkata:

- EOD: 19:00, 19:30, 20:00, 20:30.
- Event collection: 21:00; read-only event health: 23:00.
- Independent EOD watchdog: every 15 minutes from 19:00 through 23:45.
- Independent event watchdog: every 15 minutes from 21:00 through 23:45.

The existing GitHub cron expressions remain unchanged as independent backup
triggers. Hobby Vercel Schedules is beta and has up to 15-minute jitter; this
configuration does not promise exact-minute delivery or an SLA. At 23 weekdays,
the configuration produces 874 nominal executions/month, below the documented
5,000 Hobby schedule-run quota (manual invocations also consume that quota).
Function usage limits still apply.

Every dispatch carries a deterministic service/date/slot key in the GitHub run
title. Before dispatching or recovering, the worker inspects run history. A
running/queued/successful matching run is never dispatched again. Failed runs
wait at least 15 minutes before rerunning failed jobs, at most three attempts.
An ambiguous HTTP outcome is not immediately replayed; the next watchdog first
checks for the key. The workflows' concurrency and database idempotency remain
necessary: HTTP dispatch itself is at-least-once, not an exactly-once service.

Missing runs after 45 minutes, unsuccessful jobs and excessive queue/runtime
create one marked operational GitHub issue per service/date. Recovery closes
only issues owned by this controller. GitHub issue notifications depend on the
repository owner's notification settings. Credential failures or complete
scheduler outages cannot report through the same failed credential/provider;
check Vercel execution history and arrange an independent heartbeat alert if
stronger outage detection is required. Native GitHub cron remains a second clock.

No date checkpoint is moved by the scheduler. EOD recovers real missing sessions
from its last complete session; events retain their verified coverage/checkpoint
and 90-day recovery protections. An expired cross-date scheduler delivery is
skipped; the next weekday workflow recovers its bounded backlog.

## Verification

Run `npm ci --ignore-scripts` and `npm test` in this folder. Tests mock every
GitHub request and include duplicate dispatch, timeout ambiguity, missed work,
bounded retry, alert deduplication, wrong branch and timing checks.

After publishing/deploying, use the authenticated Vercel CLI with this project's
ID and inspect `vercel schedules list`, `vercel schedules invoke <name>`, and
`vercel schedules executions`. An invocation acknowledgment is not proof of
workflow completion: correlate its key with the GitHub run and inspect the
Production APIs. Test failed/missed-run recovery without synthetic writes to the
website database. Do not declare unattended operation until an actual automatic
scheduled delivery and its watchdog behavior have been observed.

The operational EOD calendar currently covers 2026 and deliberately fails
closed outside that coverage; maintain the reviewed calendar before 2027.
