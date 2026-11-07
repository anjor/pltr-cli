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
- **`functions`: `--format json` prints the SDK's own serialization**
  (camelCase API field names such as `apiName`, `dataType`, `versionId`;
  null fields left out) instead of snake_case keys with nulls. `query
  execute` and `query execute-by-rid` print the API response,
  `{"value": <result>}`.
- **`models`: `--format json` prints the SDK's own serialization** (camelCase
  API field names such as `modelApi`, `condaRequirements`, `createdTime`;
  null fields left out). `model create` and `model get` print `{"rid": ...}`
  (a model has no other fields in the API); `version list` prints
  `{"data": [...], "nextPageToken": "..."}`.
- **`orchestration`, `data-health`, `functions` and `models`: status
  messages go to stderr and errors are structured**, with the documented
  exit codes (2 usage, 3 authentication, 4 permission denied, 5 not found,
  6 validation, 7 other API or network error). Every error used to exit
  with 1. `data-health report get` no longer prints a colored status line
  to stdout; the status and message are columns of its table.
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
- **`functions` table and CSV output use curated columns** (query: API
  name, display name, description, RID, version, parameters with their
  types, output type; value type: RID, API name, display name, description,
  version, version ID, base type, constraints). `query execute` shows one
  row per item when the result is a list.
- **`models version get` takes a model version RID** as its second
  argument. Its help suggested version names such as `v1.0.0`, which the API
  rejects; find version RIDs with `pltr models version list <MODEL_RID>`.
- **`models` table and CSV output use curated columns** (version: RID,
  created, source, linked experiment, inputs, outputs, conda requirements,
  backing repositories).
- **`orchestration`, `data-health`, `functions` and `models` validate
  `--format`/`-f`:** only table, json and csv are accepted
  (case-insensitive). `-f` is new on `data-health` commands and on
  `models model get`, `version get` and `version list`; `models model
  create` keeps `-f` for `--folder`.

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
- `functions query get` and `query execute`: `--include-prerelease` and
  `--latest-version-resolution SEMANTIC_VERSION|PUBLISH_TIME` (how the
  latest version is picked when `--version` isn't given).
  `query get-by-rid` and `query execute-by-rid`: `--include-prerelease`.
- `[beta]` label in the help of every `functions` command (every Functions
  endpoint pltr calls is beta; they are always called with `preview=true`).
- `models version list --branch`, `--max-pages` and `--all` (it still
  fetches one page by default).
- `[beta]` label in the help of every `models` command (every model registry
  endpoint pltr calls is beta; they are always called with `preview=true`).
- `PLTR_FORMAT` sets the default `--format` of every `orchestration`,
  `data-health`, `functions` and `models` command.

### Changed

- `functions query execute-by-rid` looks the query up by RID
  (`Query.get_by_rid`) and then executes the version it found by API name
  (`Query.execute`), in two requests. The API has no execute-by-RID
  endpoint.

### Deprecated

- `--preview` on `orchestration schedules get`, `create` and `replace` and
  on `data-health check get`, `create`, `replace`, `delete` and
  `report get`, and on every `functions` and `models` command, is a hidden
  no-op that prints a deprecation warning; it will be removed in a future
  release. The beta endpoints are always called with `preview=true`.
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
- `functions query get-by-rid` could never succeed: it passed the RID
  positionally, but `Query.get_by_rid` takes it as the keyword `rid`.
- `functions query execute-by-rid` could never succeed: it called
  `Query.execute_by_rid`, which doesn't exist (see Changed).
- `functions query get`, `query execute` and `value-type get` only worked
  with `--preview`; they now always send `preview=true`.
- `models version get` and `models version list` could never succeed: they
  called `models.ModelVersion`, which doesn't exist. They now call the beta
  `models.Model.Version.get` / `list` with `preview=true`.
- `models model create` and `model get` only worked with `--preview`; they
  now always send `preview=true`. `model create` printed `None` as the name
  of the new model (the API returns only its RID).

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
- claude_skill/reference/functions-commands.md and claude_skill/SKILL.md:
  drop `--preview` from the options lists; document
  `--include-prerelease` and `--latest-version-resolution`, the JSON shapes
  above, and that `execute-by-rid` resolves the RID first. Point readers to
  `pltr functions query get <API name>` to find a query's RID (the example
  RID format `ri.functions.main.query.<id>` used there is unverified).
- README.md ("Model Version Operations") and
  claude_skill/reference/models-commands.md: `models version get` takes a
  model version RID, not `v1.0.0`; drop "Preview mode (`--preview`)" from
  "All Models commands support" and `--preview` from the option lists;
  mention `version list --branch/--all`. The example RIDs there
  (`ri.foundry.main.model.abc123`) are unverified.
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
- `functions query execute-by-rid` assumes that executing, by API name,
  the version `Query.get_by_rid` resolved runs the query the RID names.
- The RID formats shown in help (`ri.foundry.main.build.<id>`,
  `ri.foundry.main.job.<id>`, `ri.scheduler.main.schedule.<id>`,
  `ri.data-health.main.check.<id>`).
