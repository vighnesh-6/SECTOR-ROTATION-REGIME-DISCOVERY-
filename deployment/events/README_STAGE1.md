# Stage 1 event automation

This package runs independently of EOD portfolio processing. Research, the EOD
workflow, shared database code/schema, and website are unchanged. Historical
backfill is never called by daily automation. Static historical lists remain for
reference/legacy callers; daily collection uses official feeds and bounded official
catalogues. It never invokes the historical backfill entry point.

## Deployment status and prerequisites

Local implementation is prepared, not deployed. The production enable variable
defaults to disabled. Do not enable it until the following are verified:

1. A distinct Neon test branch with the existing project schema is supplied as
   `EVENT_TEST_DATABASE_URL`. Explicitly confirm that branch with
   `EVENT_TEST_BRANCH_CONFIRMED=true`. The integration guard rejects the known
   production endpoint, same production endpoint with/without pooler, missing
   credentials, and absent confirmation. It cannot verify Neon branch ancestry;
   the operator must confirm isolation in Neon. The supplied local test connection
   has now been independently verified as branch `br-odd-star-a1hjl6dl`, endpoint
   `ep-cold-wind-a14dq44q`. No test database is auto-created.
2. Repository Actions has `DATABASE_URL` or `NEON_DATABASE_URL` for production.
   No Neon management API key is required for the current HTTP SQL transport.
3. The offline matrix must pass on Python 3.11 and 3.13 in Actions. Local tests
   now also run on a temporary official Python 3.11.9 embeddable runtime and the
   installed Python 3.13.5. The temporary runtime is removed after verification;
   no installed interpreter or project configuration is changed.
4. Official catalogue probes and a manual dry run must succeed for the actual
   requested interval. RBI full-month press-release tables, SEBI date-filtered
   circular pages and PIB English/Delhi all-ministry monthly archives now provide
   bounded coverage receipts. PIB candidate dates are verified against actual
   release-page timestamps and release IDs. These scopes do not claim all RBI
   notifications, all SEBI publications, every PIB region/language, or every MOSPI
   publication outside PIB. Federal Reserve remains RSS-only: RSS bounds alone
   cannot establish a complete initial checkpoint, so its status remains PARTIAL.
   This remains a deployment blocker for the default four-source collector.
5. Run the isolated persistence verification, inspect preservation/concurrency
   evidence, then explicitly set `EVENT_AUTOMATION_ENABLED=true` in repository
   variables. This is an operator action; local changes do not set it.

## Workflow and modes

New workflow: `.github/workflows/daily_events.yml`.

- Weekdays 15:30 UTC / 21:00 IST: collection.
- Weekdays 17:30 UTC / 23:00 IST: **read-only** freshness monitoring.
- Manual default: `dry-run`; optional modes: `test-live`, `live`, `health`.
- Manual recent lookback 1-90 days; optional recent `start_date` cannot skip an
  earlier source checkpoint. Inputs are passed as quoted arguments via env vars.
- Serial workflow concurrency, bounded HTTP and transaction retries, job timeouts,
  source-level status and an Actions step summary. Partial and failed runs exit 1.
- Enable GitHub failure notifications for the operator. The health schedule can
  detect a missed collection run, but GitHub cannot independently alert if both
  schedules fail to start. External uptime monitoring can invoke the read-only
  health command for that requirement; no external notification service is
  silently configured by this package.

GitHub schedules are best-effort and require the workflow on the default branch.
Commit/push are performed manually by the owner. Review only Stage 1 paths; the
working tree already contained unrelated website and test edits before this work.

## Safety, persistence, and recovery

`macro_events` is append-only: no UPDATE, DELETE, TRUNCATE, schema changes, or
historical backfill. Existing schema serialization is retained. Original source
URLs and stable URL hashes are included in the execution log's source references.

Persistence re-reads existing events, applies existing deduplication, then sends
conditional inserts in one Neon **Serializable** HTTP batch transaction. Database
predicate reads protect concurrent event collectors; serialization failures retry
the whole batch. Conditions reject equal normalized titles, stable official URL
hashes, and conservative same-date/category title overlap with matching numbers.
This prevents ordinary title variants from being inserted again without adding a
unique constraint or modifying the schema. All writers must use the guarded
path; arbitrary external SQL writers are outside this concurrency contract.
Ambiguous HTTP outcomes are retried with the same conditional inserts; insertion
counts in the eventual response may exclude rows committed before a lost response.
PostgreSQL SSI, SQL syntax, concurrent execution and preservation have been tested
against the isolated Neon branch, without connecting to production. Reused string
parameters in the INSERT projection are explicitly cast to text to avoid 42P08.

Live runs create their own `pipeline_execution_logs` row using RETURNING log_id,
and update only that newly created row. Existing logs are not rewritten. Dry run
and health modes issue no database writes, including no execution-log writes.

Each successful source's end date is recovered from completed event logs. Failed
sources retain their previous cursor. Requests overlap the cursor by at least two
days. Requested lookback, requested window, previous checkpoint, effective window,
extension days, visible oldest/newest RSS dates, and unavailable intervals are
reported separately. The parser already calculated `oldest_publication`; it is
not replaced with a guessed date or the oldest policy-only event. A gap beyond
feed retention or 90 days fails with `recovery_required=true`;
the cursor does not advance. Official archive recovery requires a source capable
of supplying that window, and must not use the historical backfill runner. Until
then other sources can progress with a PARTIAL status. With no checkpoint, the
requested start is the required bootstrap boundary; unavailable initial history
is explicitly blocked rather than silently treated as covered. Existing-checkpoint
protection retains the saved boundary and overlapping window. RSS may lack older
lookback dates, but a complete official receipt must cover the entire effective
window before a new checkpoint advances. RSS retention is not a guarantee of
complete historical event coverage.

Every rejected RSS item is counted with a stable reason and item position (the
detail list is capped at 20, counts are not). Entirely invalid feeds fail; mixed
feeds retain valid in-window events only when coverage protection passes, remain
PARTIAL, and retain the previous checkpoint. Retrying corrected feeds is
idempotent. No archive recovery is fabricated from static historical lists.

Exception messages and nested diagnostics are sanitized before execution logging
or summaries. In GitHub Actions, full chained tracebacks (without captured locals)
are redacted before emission. Connection URLs, credentials, environment secrets,
Bearer/Basic authorization values and common key/value secret formats are masked.

## Validation commands

From repository root with the chosen interpreter, disable bytecode/cache writes:

```
python -B -m pytest -q -p no:cacheprovider deployment/tests/test_event_ingestion.py deployment/tests/test_event_automation.py deployment/tests/test_event_feed_recovery.py deployment/tests/test_event_archives.py
python -B -m deployment.events.daily_collector --days 14
python -B -m deployment.events.daily_collector --check-health
```

For offline tests, set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` in the process environment.
The first command is offline; the latter two need the configured database and the
collector also reads official public feeds. Do not run `--live` for testing on
production.

Only after configuring the explicitly confirmed isolated test branch:

```
python -B -m pytest -q -p no:cacheprovider deployment/tests/test_event_neon_persistence.py
```

This opt-in test appends a UUID-labelled synthetic event and a new execution log
to the test branch. It tests two concurrent writers, a repeated insert, dry-run
behaviour, returned logging identity, and exact preservation of all pre-existing
event rows. It does not delete fixtures or reset sequences. Never point it at
production. Missing isolation configuration fails before creating a client.

## Current local evidence

- Existing and new offline event tests pass (see final task report for count).
- Actual Python 3.11.9 and 3.13.5 offline execution is checked, as well as 3.11 syntax.
- Workflow YAML and safety contracts are tested locally; actionlint and actual
  GitHub execution are not verified here.
- The isolated test branch passed persistence, concurrent insertion, duplicate
  prevention, partial-feed retry/checkpoint behaviour, lost-acknowledgement recovery,
  and transaction rollback checks. Test-created fixtures/logs were cleaned up;
  all 230 pre-existing event rows were compared and preserved exactly. Sequences
  were not reset. No production database was accessed.
- Live RBI/SEBI feeds exposed oldest dates of 2026-11-06 during diagnosis; no
  source checkpoints existed in the isolated branch. No production checkpoint
  dates are claimed or queried. Older saved-cursor gaps are regression-tested.
- GitHub secrets, live workflow execution, and repository enable-variable state
  remain unverified. Production collection was not enabled. Federal Reserve
  catalogue completeness remains unverified; it cannot advance its checkpoint.

## Official coverage and bootstrap evidence

`coverage_verification.json` records the read-only 2026-10-09 through 2026-11-08
probe using only the isolated branch. It contains public document IDs, listing
dates/URLs, response hashes and retrieval times, filter/pagination receipts,
rejections and database duplicate counts. No credentials or existing database
rows are included. Receipts describe the public catalogues as observed, not a
guarantee that a publisher never omits a document or revises its archive.

- RBI: submit each requested month through the official press-release page's
  existing form; require the month echo, dated rows, unique PRIDs, and no paging
  controls. Unexpected markup, empty months or unsupported pagination fail closed.
- SEBI: follow the official circular listing's AJAX pagination with explicit date
  filters. Require contiguous ranges, invariant total, unique IDs and in-range
  dates. An unrecognised empty-result format fails closed.
- PIB: submit All Days/All Ministries for each month, with English/Delhi scope;
  require the echoed filters and declared count to match all parsed unique IDs.
  Relevant releases require matching document identity and actual Posted On time.

Only complete receipts spanning the entire effective window permit source OK and
checkpoint advancement. RSS-only bounds cannot certify completeness. Legacy OK
logs retain their earliest boundary as a conservative recovery anchor until a
verified receipt supersedes it; they cannot silently reset the requested start.
Initial deployment must explicitly approve its
bounded collection start and verify the interval; this does not certify history
before that start. Older missing intervals require separate approval and verified
official evidence, never a manual cursor advance or a historical-backfill rerun.

## Implementation references

- Neon HTTP batch transaction headers follow the official driver implementation:
  https://github.com/neondatabase/serverless/blob/main/src/http/index.ts
- SEBI's official RSS announcement: https://www.sebi.gov.in/rss.html
- PIB's published English/regional RSS parameters:
  https://www.pib.gov.in/ViewRss.aspx?lang=1&reg=3
- GitHub scheduling semantics:
  https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
