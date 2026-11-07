### Breaking

- **`orchestration`: `--format json` prints the SDK's own serialization.**
  Field names are the Foundry API's (camelCase, for example `branchName`,
  `jobStatus`, `createdTime`), null fields are left out, and there are no
  hand-picked snake_case keys any more. `builds jobs`, `builds search` and
  `schedules runs` print `{"data": [...], "nextPageToken": "..."}`.
  `builds get-batch` and `jobs get-batch` print the API response,
  `{"data": {"<RID>": {...}}}`. `builds cancel`, `schedules delete`,
  `schedules pause` and `schedules unpause` print `null`.
- **`data-health`: `--format json` prints the SDK's own serialization**
  (camelCase API field names such as `createdBy`, `updatedTime`,
  `statusCheckConfig`; null fields left out) instead of snake_case keys with
  nulls. `report latest` prints the API response `{"data": [...]}`;
  `check delete` prints `null`.
- **`orchestration` and `data-health`: status messages go to stderr and
  errors are structured**, with the documented exit codes (2 usage,
  3 authentication, 4 permission denied, 5 not found, 6 validation, 7 other
  API or network error). Every error used to exit with 1. `data-health
  report get` no longer prints a colored status line to stdout; the status
  and message are columns of its table.
- **`orchestration builds cancel` and `orchestration schedules replace` ask
  for confirmation.** `--yes`/`-y` skips it. When stdin is not a terminal
  they (and `schedules delete`) fail with exit code 2 unless `--yes` is
  given; `schedules delete` used to prompt.
- **`data-health check replace` asks for confirmation**, and
  `data-health check delete` no longer prompts when stdin is not a terminal:
  without `--yes`/`-y` both fail with exit code 2.
- **`data-health check delete --force`/`-f` is replaced by `--yes`/`-y`.**
  `--force` still works for one release as a hidden, deprecated alias of
  `--yes`. Its short form `-f` is gone: `-f` is now `--format`, as on every
  converted command.
- **`data-health report get` takes the check RID first:**
  `pltr data-health report get <CHECK_RID> <CHECK_REPORT_RID>`. The API
  addresses a report through its check; the old one-argument form could
  never succeed. Find report RIDs with the new `data-health report latest`.
- **`orchestration builds search` requires a filter** (`--where` or one of
  the new filter options; see Added). The API requires one; the command
  could never succeed without it.
- **`orchestration` table and CSV columns changed.** They now read real
  fields of the SDK models. The old columns read fields that don't exist
  (`started_time` and `commit_hash` of builds, `status`, `job_type` and
  `created_time` of jobs, `modified_time`/`modified_by` of schedules, and
  `status`, `started_time`, `finished_time` and `build_rid` of schedule runs)
  and were always empty.
- **`orchestration schedules run` prints the schedule run** (its result and
  the build it started) instead of only a success message.
- **`data-health` table and CSV output use curated columns** (check: RID,
  type, intent, groups, created by, updated, config; report: RID, status,
  message, created, check, check type) instead of every key of the
  serialized response.
- **`orchestration` and `data-health` validate `--format`/`-f`:** only
  table, json and csv are accepted (case-insensitive). `-f` is new on
  `data-health` commands.

### Added

- `orchestration builds search` filters: `--where` (the API's
  `SearchBuildsFilter` as JSON or `@file.json`), `--status`, `--branch`,
  `--created-by`, `--started-after`, `--started-before`, `--finished-after`,
  `--finished-before` (ISO-8601 timestamps with a time zone), combined with
  AND, and `--order-by STARTED_TIME|FINISHED_TIME[:ASC|DESC]`.
- `orchestration builds create --fallback-branch` (repeatable; it was always
  sent empty), `--retry-count` and `--output`. TARGET accepts `@file.json`.
- `orchestration schedules create`/`replace --scope-mode` (JSON or
  `@file.json`). ACTION and `--trigger` accept `@file.json`. `--output` on
  `schedules create`, `replace` and `run`.
- `orchestration builds get-batch` and `jobs get-batch` take RIDs separated
  by spaces as well as commas.
- `--page-token`, `--max-pages` and `--all` on `orchestration builds jobs`;
  `--max-pages` and `--all` on `orchestration schedules runs`. Both still
  fetch one page by default.
- `[beta]` label in the help of `orchestration builds search`, `jobs get`,
  `jobs get-batch`, `schedules get`, `schedules create` and
  `schedules replace`: they call beta Foundry endpoints, always with
  `preview=true`.
- `data-health report latest <CHECK_RID> [--limit N]`
  (`Check.CheckReport.get_latest`): a check's most recent reports, the way
  to find the report RIDs that `report get` needs.
- `[beta]` label in the help of every `data-health` command (all data
  health endpoints are beta; they are always called with `preview=true`).
- `PLTR_FORMAT` sets the default `--format` of every `orchestration` and
  `data-health` command.

### Deprecated

- `--preview` on `orchestration schedules get`, `create` and `replace` and
  on `data-health check get`, `create`, `replace`, `delete` and
  `report get` is a hidden no-op that prints a deprecation warning; it will
  be removed in a future release. The beta endpoints are always called with
  `preview=true`.
- `data-health check delete --force` is a hidden, deprecated alias of
  `--yes`.

### Fixed

- `orchestration builds get-batch` and `jobs get-batch` could never succeed:
  they sent `{"rid": ...}` request elements, but the API (and the SDK)
  require `{"buildRid": ...}` / `{"jobRid": ...}`.
- `orchestration builds search` could never succeed: it called the beta
  `Build.search` without the required `where` filter, and its "retry without
  preview" fallback could never run.
- `orchestration jobs get` and `jobs get-batch` called beta endpoints
  without `preview=true`, so the server rejected them.
- `orchestration schedules get`, `create` and `replace` only worked with
  `--preview`; they now always send `preview=true`.
- `data-health report get` could never succeed: it called
  `data_health.CheckReport.get`, which doesn't exist. It now calls
  `Check.CheckReport.get(check_rid, check_report_rid)`.
- `data-health check create`, `get`, `replace` and `delete` only worked
  with `--preview`; they now always send `preview=true`.
- The `data-health check create` help example used the severity `WARNING`,
  which the API rejects; severities are `MODERATE` and `CRITICAL`.

### Docs to update

- `orchestration builds search` without a filter no longer works (it never
  did): add a filter such as `--status FAILED` or `--branch master` in
  README.md (lines with `pltr orchestration builds search`),
  docs/pagination.md, docs/migration/v2-pagination.md,
  docs/user-guide/quick-start.md, docs/user-guide/workflows.md,
  docs/user-guide/commands.md (`builds search` section),
  claude_skill/SKILL.md, claude_skill/workflows/data-pipeline.md,
  claude_skill/workflows/data-analysis.md and
  claude_skill/reference/orchestration-commands.md.
- docs/user-guide/commands.md and claude_skill/reference/orchestration-commands.md:
  drop `--preview` from `schedules get` examples; document `--yes` on
  `builds cancel` and `schedules replace`, the new `builds search` filters,
  `builds create --fallback-branch/--retry-count`, `schedules create
  --scope-mode`, and that `schedules run` prints the run and its build.
- The orchestration formatters in `src/pltr/utils/formatting.py`
  (`format_build_detail`, `format_builds_list`, `format_job_detail`,
  `format_jobs_list`, `format_schedule_detail`, `format_schedules_list`,
  `format_schedule_runs_list`) are no longer used and can be deleted.

### Not verified live

- `orchestration builds search`: the time filters send ISO-8601 UTC
  timestamps (`2024-01-31T00:00:00Z`) as the filter `value`, and
  `--created-by` sends a user ID; the SDK types these values as `Any`, so
  the accepted formats need a live check.
- `orchestration schedules replace` is documented as a full replacement
  (fields you don't pass aren't kept), based on it being an HTTP PUT whose
  optional fields the SDK leaves out when unset.
- The RID formats shown in help (`ri.foundry.main.build.<id>`,
  `ri.foundry.main.job.<id>`, `ri.scheduler.main.schedule.<id>`).
