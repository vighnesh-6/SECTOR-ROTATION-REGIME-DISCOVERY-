# Stage 1 event automation

This package runs independently of EOD portfolio processing. Research, the EOD
workflow, shared database code/schema, and website are unchanged. Historical
backfill is never called by daily automation. Static historical lists remain for
reference/legacy callers; `fetch_incremental` uses only live official feeds.

## Deployment status and prerequisites

Local implementation is prepared, not deployed. The production enable variable
defaults to disabled. Do not enable it until the following are verified:

1. A distinct Neon test branch with the existing project schema is supplied as
   `EVENT_TEST_DATABASE_URL`. Explicitly confirm that branch with
   `EVENT_TEST_BRANCH_CONFIRMED=true`. The integration guard rejects the known
   production endpoint, same production endpoint with/without pooler, missing
   credentials, and absent confirmation. It cannot verify Neon branch ancestry;
   the operator must confirm isolation in Neon. No test database is auto-created.
2. Repository Actions has `DATABASE_URL` or `NEON_DATABASE_URL` for production.
   No Neon management API key is required for the current HTTP SQL transport.
3. The offline matrix passes on Python 3.11 and 3.13 in Actions. Locally available
   Python is 3.13.5; local 3.11 execution has not been verified.
4. Official source probes and a manual dry run succeed. In the implementation
   session RBI, Fed and SEBI parsed successfully. PIB returned Hindi RSS items
   without publication dates even with the advertised English query parameters;
   a separate official MOSPI RSS probe failed. MOSPI/PIB coverage is **blocked**,
   not silently classified as a successful empty source. Do not invent dates,
   ingest static historical lists, disable TLS checks, or enable production until
   a functioning official dated feed/approved adapter resolves this blocker.
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
PostgreSQL SSI, SQL syntax, concurrent execution and preservation against actual
Neon remain subject to the isolated integration verification.

Live runs create their own `pipeline_execution_logs` row using RETURNING log_id,
and update only that newly created row. Existing logs are not rewritten. Dry run
and health modes issue no database writes, including no execution-log writes.

Each successful source's end date is recovered from completed event logs. Failed
sources retain their previous cursor. Requests overlap the cursor by at least two
days. A gap beyond feed retention or 90 days fails with `recovery_required=true`;
the cursor does not advance. Official archive recovery requires a source capable
of supplying that window, and must not use the historical backfill runner. Until
then other sources can progress with a PARTIAL status. The first run scans the
recent 14-day window, not the historical project period. RSS retention is not a
guarantee of complete historical event coverage.

## Validation commands

From repository root with the chosen interpreter, disable bytecode/cache writes:

```
python -B -m pytest -q -p no:cacheprovider deployment/tests/test_event_ingestion.py deployment/tests/test_event_automation.py
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
- Python 3.11 syntax compatibility and local 3.13 imports are checked separately.
- Workflow YAML and safety contracts are tested locally; actionlint and actual
  GitHub execution are not verified here.
- No production or test-branch database writes were performed in this session.
- No actual 230-row preservation or live concurrency claim is made from mocks.
- Missing test branch and GitHub access prevent remote production completion.

## Implementation references

- Neon HTTP batch transaction headers follow the official driver implementation:
  https://github.com/neondatabase/serverless/blob/main/src/http/index.ts
- SEBI's official RSS announcement: https://www.sebi.gov.in/rss.html
- PIB's published English/regional RSS parameters:
  https://www.pib.gov.in/ViewRss.aspx?lang=1&reg=3
- GitHub scheduling semantics:
  https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
