# Command Reference

Every curated pltr command, by group, with examples. Each command's `--help`
lists all of its options; this page explains what the commands are for and
how they fit together. For the generated commands that mirror the SDK one to
one, see [`pltr api`](../api-commands.md).

## How every command works

- **Help**: `pltr --help`, `pltr <group> --help` and `pltr <command> --help`.
  To find a command for a task, search the manifest:
  `pltr commands search "list dataset files"`.
- **Profiles**: `--profile NAME` (`-p` on most commands) picks the
  credentials; see [Authentication](authentication.md).
- **Output**: `--format table|json|csv` (`-f`) and `--output FILE` (`-o`).
  The default is `table`; set `PLTR_FORMAT=json` to change it. JSON is the
  Foundry API's own shape (camelCase field names, null fields left out), and
  stdout carries only data: messages, warnings, prompts and errors go to
  stderr. Exit codes and error JSON are described in the README's
  [Output, errors and exit codes](../../README.md#output-errors-and-exit-codes).
- **Paging**: commands marked *paged* fetch one page by default and take
  `--page-size`, `--page-token` (resume from an earlier `nextPageToken`),
  `--max-pages N` and `--all`. See [Pagination](../pagination.md).
- **Confirmation**: commands marked *asks first* ask on stderr before they
  change anything; `--yes` (`-y`) skips the question. Without a terminal on
  stdin they never prompt: they exit with code 2 unless you pass `--yes`.
- **Beta**: commands whose help starts with `[beta]` call beta Foundry
  endpoints. pltr sends `preview=true` for you; beta endpoints can change
  without notice.
- **RIDs**: most arguments are Resource Identifiers, such as
  `ri.foundry.main.dataset.<uuid>`. The examples below use placeholders like
  `<dataset-rid>`.

Contents: [Setup](#setup-configure-verify-commands) ·
[Datasets](#datasets-pltr-dataset) · [Copying](#copying-pltr-cp) ·
[Filesystem](#filesystem-folder-space-project-resource-resource-role) ·
[Ontology](#ontology-pltr-ontology) · [SQL](#sql-pltr-sql) ·
[Orchestration](#orchestration-pltr-orchestration) ·
[Data health](#data-health-pltr-data-health) ·
[Functions](#functions-pltr-functions) · [Models](#models-pltr-models) ·
[Streams](#streams-pltr-streams) · [Media sets](#media-sets-pltr-media-sets) ·
[Connectivity](#connectivity-pltr-connectivity) ·
[Language models](#language-models-pltr-language-models) ·
[AIP agents, widgets and third-party apps](#aip-agents-widgets-and-third-party-apps) ·
[Audit logs](#audit-logs-pltr-audit) · [Admin](#admin-pltr-admin) ·
[Aliases, shell and completion](#aliases-shell-and-completion)

## Setup: `configure`, `verify`, `commands`

A profile holds a Foundry host and credentials; the credentials go to the
system keyring. The first profile you create becomes the default. Without a
profile, pltr can use `FOUNDRY_HOST` with `FOUNDRY_TOKEN` (or
`FOUNDRY_CLIENT_ID` and `FOUNDRY_CLIENT_SECRET`) instead; see
[Authentication](authentication.md).

| Command | What it does |
|---|---|
| `configure configure` | Create a profile, or replace an existing one (asks first) |
| `configure list-profiles` | List the profiles and which one is the default |
| `configure set-default PROFILE` | Make a profile the default |
| `configure delete PROFILE` | Delete a profile and its stored credentials (asks first) |
| `verify` | Check the credentials: fetch your user and show where the credentials came from |
| `commands list [PATH]...` | List every command; with `--format json`, the whole manifest |
| `commands search TEXT...` | Search commands by name, description and SDK method, best match first |
| `commands show COMMAND...` | Show one command's manifest entry: usage, arguments, options and more |

```bash
# Interactive: prompts for the host, the auth type and the credentials
pltr configure configure

# Non-interactive (no prompts without a terminal: pass every value)
pltr configure configure --profile prod --auth-type token \
  --host foundry.company.com --token "$FOUNDRY_TOKEN"
pltr configure configure --profile dev --auth-type oauth \
  --host dev.foundry.com --client-id "$CLIENT_ID" --client-secret "$CLIENT_SECRET"

pltr configure list-profiles
pltr configure set-default prod
pltr configure delete old-profile --yes

# Check authentication (exit code 3: no usable or rejected credentials)
pltr verify
pltr verify --profile dev --format json   # {"authSource": {...}, "user": {...}}

# Find commands
pltr commands search "list dataset branches"
pltr commands show dataset branches list --format json
pltr commands list api datasets
```

`pltr verify` fetches your user with the SDK's `User.get_current`; OAuth
clients need the `api:admin-read` scope for it, or verify exits with code 4.
`pltr commands` makes no Foundry call.

## Datasets: `pltr dataset`

Datasets are addressed by RID (`ri.foundry.main.dataset.<uuid>`). Commands
that take `--branch` default to the dataset's default branch (`master` on
most enrollments). Files change in transactions: you open one, upload or
delete files in it, and commit it to make the changes visible (or abort it).

| Command | What it does |
|---|---|
| `dataset get` | Get a dataset's metadata: its RID, name and parent folder |
| `dataset create` | Create an empty dataset in a project or folder |
| `dataset preview` | Read rows of a dataset as a table, JSON or CSV |
| `dataset branches list` | List a dataset's branches (paged) |
| `dataset branches create` | Create a branch, starting from a parent branch or a transaction |
| `dataset branches get` | Get a branch: its name and latest open or committed transaction |
| `dataset branches delete` | Delete a branch, but not master (asks first) |
| `dataset branches transactions` | [beta] List a branch's transactions, newest first (paged) |
| `dataset files list` | List the files in a dataset's current view of a branch (paged) |
| `dataset files upload` | Upload a local file or directory to a dataset (asks first for a SNAPSHOT) |
| `dataset files get` | Download a file, or a folder with `--recursive`, from a dataset |
| `dataset files delete` | Delete a file from a dataset's current view (asks first) |
| `dataset files info` | Get a file's metadata: path, size, last update and transaction |
| `dataset transactions start` | Open a transaction on a branch (one open transaction per branch) |
| `dataset transactions commit` | Commit an open transaction, making its changes visible |
| `dataset transactions abort` | Abort an open transaction, discarding its changes (asks first) |
| `dataset transactions status` | Get a transaction: type, status (OPEN, COMMITTED, ABORTED) and times |
| `dataset transactions list` | [beta] List a dataset's transactions, newest first (paged) |
| `dataset transactions build` | [beta] Get the RID of the build that computed a transaction |
| `dataset views create` | Create a view: a virtual dataset that unions its backing datasets |
| `dataset views get` | Get a view: its backing datasets, primary key and parent folder |
| `dataset views add-datasets` | Add backing datasets to a view |
| `dataset views remove-datasets` | Remove backing datasets from a view (asks first) |
| `dataset views replace-datasets` | Replace all of a view's backing datasets (asks first) |
| `dataset views add-primary-key` | Add a primary key to a view that has none |
| `dataset schema get` | Get a dataset's schema |
| `dataset schema set` | Replace a dataset's schema on a branch (asks first) |
| `dataset schema apply` | Infer a dataset's schema from its files and apply it (asks first) |
| `dataset schedules list` | List the RIDs of the schedules that target a dataset (paged) |
| `dataset jobs list` | [beta] List the RIDs of a dataset's jobs, newest first (paged) |

```bash
# Metadata, rows and schema
pltr dataset get <dataset-rid>
pltr dataset preview <dataset-rid> --limit 20 --column name --column revenue
pltr dataset schema get <dataset-rid> --format json

# Create a dataset in a project or folder
pltr dataset create "Sales 2026" --parent-folder <project-or-folder-rid>

# Files: list, download one, download a folder, print one to stdout
pltr dataset files list <dataset-rid> --path-prefix raw/
pltr dataset files get <dataset-rid> raw/sales.csv sales.csv
pltr dataset files get <dataset-rid> raw ./raw --recursive
pltr dataset files get <dataset-rid> raw/sales.csv - | head

# Upload one file (the API commits it at once), or a directory in one
# transaction that pltr opens and commits (SNAPSHOT replaces every file, so
# it asks first; --yes skips the question)
pltr dataset files upload sales.csv <dataset-rid> --path raw/sales.csv
pltr dataset files upload ./exports <dataset-rid> --path raw --transaction-type SNAPSHOT --yes

# Several uploads in one transaction of your own
TXN=$(pltr dataset transactions start <dataset-rid> --type APPEND --format json | jq -r .rid)
pltr dataset files upload a.csv <dataset-rid> --transaction-rid "$TXN"
pltr dataset files upload b.csv <dataset-rid> --transaction-rid "$TXN"
pltr dataset transactions commit <dataset-rid> "$TXN"

# Branches
pltr dataset branches list <dataset-rid>
pltr dataset branches create <dataset-rid> feature-x --parent master
pltr dataset branches delete <dataset-rid> feature-x --yes

# Schema: infer it from the uploaded CSV files, or set it yourself
pltr dataset schema apply <dataset-rid> --yes
pltr dataset schema set <dataset-rid> --from-csv sales.csv --yes
pltr dataset schema set <dataset-rid> --json @schema.json --dataframe-reader CSV --yes

# Views
pltr dataset views create "All regions" --parent-folder <project-or-folder-rid> \
  --backing-dataset <dataset-rid> --backing-dataset <other-dataset-rid>@master
pltr dataset views add-primary-key <view-rid> order_id --latest-wins updated_at
```

Notes:

- `files get` streams to disk and never leaves a partial file. With `-` as
  the output path, the content goes to stdout and the metadata isn't printed.
  `files get --recursive` refuses, before writing any file, a dataset path
  that can't be written safely inside the output directory: a `..` part, a
  symlink out of it, or on Windows a `\` or `:` in a name.
- `schema set --json` takes the API's `{"fieldSchemaList": [...]}`, the JSON
  output of `schema get`, or the older `{"fields": [...]}` form, inline or as
  `@file.json`. `--from-csv FILE` infers the column types from the header and
  first 100 rows of a local CSV: `BOOLEAN` (only `true`/`false`), `INTEGER` or
  `LONG` (by size), `DOUBLE`, `DATE`, `TIMESTAMP`, else `STRING`. The
  confirmation prompt lists the fields it will set.
- `schema apply` calls the endpoints Foundry's web interface uses for schema
  inference (direct HTTP, not the SDK). Its `--branch` defaults to `master`.
- `branches create` starts the new branch at the parent's latest transaction,
  which must be committed: if it is still open, commit or abort it first, or
  pass `--transaction-rid` with a committed transaction (`branches
  transactions <dataset-rid> <parent>` lists them, newest first).
- `transactions list` lists every branch's transactions unless you pass
  `--branch`. `schedules list` prints RIDs only, as the API returns them.
- JSON output: a transaction's RID is `.rid`; `preview` prints
  `{"data": [{column: value}]}` with BINARY values in base64.

## Copying: `pltr cp`

`pltr cp SOURCE_RID TARGET_FOLDER_RID` copies a dataset, or a folder and
everything in it with `--recursive`, into another folder or a project.

```bash
pltr cp <dataset-rid> <target-folder-rid>
pltr cp <dataset-rid> <target-folder-rid> --branch develop --no-schema
pltr cp <folder-rid> <target-folder-rid> --recursive --name-suffix "-copy"
pltr cp <folder-rid> <target-folder-rid> --recursive --dry-run
```

- A dataset copy gets the files of `--branch`, committed in one SNAPSHOT
  transaction on the same branch of the copy, which cp creates first when it
  isn't the copy's default branch. Then, with `--schema` (the default), the
  source's schema on that branch is put on the committed copy; a source
  without a schema is copied without one. The API doesn't report the
  source's dataframe reader, so the copy's schema gets `CSV` when every file
  is a `.csv` file, `AVRO` when every file is `.avro`, and otherwise the
  API's default (`PARQUET`). A source with no files on the branch gives an
  empty copy with no schema.
- If any step of a dataset copy fails, including the schema, the partial
  copy is moved to the trash and pltr exits with the error. `--no-schema`
  copies only the files.
- A folder copy recreates its subfolders and datasets; other resource types
  are skipped with a warning. When some items fail, the others are still
  copied (unless `--fail-fast`), and pltr exits with the first failure's
  error. The target can't be the folder itself or a folder inside it (exit
  2).
- It prints the resources it created (JSON: `{"data": [...]}`, the API's
  `Folder` and `Dataset` objects) and its progress on stderr. `--dry-run`
  creates nothing and prints the resources it would copy.

## Filesystem: `folder`, `space`, `project`, `resource`, `resource-role`

Compass is Foundry's filesystem: spaces hold projects, and projects hold
folders and resources such as datasets. Project and folder RIDs look like
`ri.compass.main.folder.<uuid>`. Find RIDs with `pltr space list`,
`pltr project list`, `pltr folder list` and `pltr resource get-by-path`.

| Command | What it does |
|---|---|
| `folder create` | Create a folder inside a project or another folder |
| `folder get` | Get a folder's metadata |
| `folder list` | List the resources directly inside a folder or project (paged) |
| `folder batch-get` | Get several folders in one request |
| `space create` | [beta] Create a space |
| `space get` | [beta] Get a space's metadata |
| `space list` | List the spaces you can see (paged) |
| `space update` | [beta] Change a space's name, description, default role set or usage account |
| `space delete` | [beta] Delete an empty space (asks first) |
| `project create` | Create a project in a space |
| `project get` | Get a project's metadata |
| `project list` | List the projects in a space, or in every space you can see (paged) |
| `project update` | [beta] Change a project's display name or description |
| `project delete` | Move a project, and everything in it, to the trash (asks first) |
| `project add-orgs` | Apply organizations to a project; they must also be on its space |
| `project remove-orgs` | Remove organizations from a project (asks first) |
| `project list-orgs` | List the RIDs of the organizations applied directly to a project (paged) |
| `project create-from-template` | Create a project from a project template |
| `resource get` | Get a resource's metadata by RID |
| `resource get-by-path` | Get a resource's metadata by its path |
| `resource list` | List the resources directly inside a folder (paged) |
| `resource search` | Find resources below a folder by name, path, description, RID or type |
| `resource batch-get` | Get several resources in one request |
| `resource batch-get-by-path` | Get several resources by path in one request |
| `resource delete` | Move a resource to the trash (asks first) |
| `resource restore` | Restore a resource, and its directly trashed ancestors, from the trash |
| `resource permanently-delete` | Permanently delete a resource that is in the trash (asks first) |
| `resource add-markings` | Apply markings to a resource |
| `resource remove-markings` | Remove markings from a resource (asks first) |
| `resource list-markings` | List the IDs of the markings applied directly to a resource (paged) |
| `resource access-requirements` | Show the organizations and markings a user needs to view a resource |
| `resource-role grant` | Grant a role on a resource to a user, a group or everyone |
| `resource-role revoke` | Revoke a role on a resource (asks first) |
| `resource-role list` | List the role grants on a resource (paged) |

```bash
# Find your way around
pltr space list
pltr project list --space-rid <space-rid>
pltr folder list <project-or-folder-rid> --all
pltr resource get-by-path "/My Space/My Project/sales"
pltr resource search sales --folder-rid <project-rid> --type dataset

# Folders and projects
pltr folder create "Reports" --parent-folder <project-or-folder-rid>
pltr project create "Forecasting" --space-rid <space-rid> --description "Demand forecasts"
pltr project update <project-rid> --description "Demand and supply forecasts"
pltr project delete <project-rid> --yes     # moves it to the trash
pltr resource restore <project-rid>

# Spaces
pltr space create "Analytics" --enrollment-rid <enrollment-rid> \
  --organization <organization-rid> --deletion-policy-org <organization-rid>
pltr space update <space-rid> --description "Shared analytics work"

# Trash and markings
pltr resource delete <resource-rid> --yes
pltr resource permanently-delete <resource-rid> --yes
pltr resource add-markings <resource-rid> --marking <marking-id>
pltr resource list-markings <resource-rid>

# Role grants
pltr resource-role list <resource-rid> --include-inherited
pltr resource-role grant <resource-rid> --principal-id <user-or-group-id> --role <role-id>
pltr resource-role grant <resource-rid> --everyone --role <role-id>
pltr resource-role revoke <resource-rid> --principal-id <user-or-group-id> --role <role-id> --yes
```

Notes:

- `folder create` and `dataset create` need a parent project or folder:
  folders can't be created directly in a space.
- `resource-role grant` and `revoke` take user and group IDs (UUIDs), not
  names: find them with `pltr admin user search` and
  `pltr admin group search`. Role IDs come from the role set of the
  resource's space (`compass:manage` is Owner in Foundry's default role set);
  `pltr resource-role list` shows the ones in use.
- `resource search` scans folders, because the API has no search endpoint:
  start from the narrowest `--folder-rid` you can. It stops after
  `--max-folders` folders (default 1000) and warns that the results may be
  incomplete. `--type` takes API type names such as `FOUNDRY_DATASET` or
  `COMPASS_FOLDER` (`dataset` and `folder` work too).
- `project list` without `--space-rid` lists every space's projects (all
  pages; `--page-token` and `--max-pages` need `--space-rid`).
- `project update` and `space update` send back the fields you don't change,
  so they keep their values.
- `project list-orgs` and `resource list-markings` print IDs only, as the API
  returns them.

## Ontology: `pltr ontology`

The ontology argument is the ontology's API name or RID; object types,
link types, actions and queries are named by API name. JSON inputs
(`--where`, `--aggregation`, `--group-by`, `--order-by`, action parameters
and batch requests) use the Foundry API's shapes, inline, as `@file.json` or
as `@-` for stdin, and are checked against the SDK's models before anything
is sent.

| Command | What it does |
|---|---|
| `ontology list` | List the ontologies you can see |
| `ontology get` | Get an ontology's metadata |
| `ontology object-type-list` | List an ontology's object types (paged) |
| `ontology object-type-get` | Get an object type: its primary key, title property and properties |
| `ontology object-type-create` | Create an object type (direct HTTP: the SDK can't create object types) |
| `ontology link-type-create` | Create a link type (direct HTTP: the SDK can't create link types) |
| `ontology object-list` | List the objects of an object type (paged) |
| `ontology object-get` | Get an object by primary key |
| `ontology object-search` | Search the objects of an object type with a typed query (paged) |
| `ontology object-aggregate` | Aggregate objects: counts, sums, averages and more, optionally grouped |
| `ontology object-count` | [beta] Count the objects of an object type |
| `ontology object-linked` | List the objects linked to an object through a link type (paged) |
| `ontology action-apply` | Apply an action: validate its parameters and make its edits |
| `ontology action-validate` | Check an action's parameters without applying it |
| `ontology action-apply-batch` | Apply several actions of one action type in a single request |
| `ontology query-execute` | Execute an ontology query function |

```bash
pltr ontology list
pltr ontology object-type-list <ontology>
pltr ontology object-type-get <ontology> Employee --format json

# Objects
pltr ontology object-list <ontology> Employee --properties name,department --page-size 50
pltr ontology object-get <ontology> Employee E-12345
pltr ontology object-linked <ontology> Employee E-12345 reportsTo

# Search with the API's typed query (there is no free-text search)
pltr ontology object-search <ontology> Employee \
  --where '{"type": "eq", "field": "department", "value": "Engineering"}' --all

# Count and aggregate
pltr ontology object-count <ontology> Employee
pltr ontology object-aggregate <ontology> Employee \
  --aggregation '[{"type": "count", "name": "employees"}, {"type": "avg", "field": "salary", "name": "avgSalary"}]' \
  --group-by department

# Actions: validate, then apply
pltr ontology action-validate <ontology> promote-employee '{"employee": "E-12345", "level": 5}'
pltr ontology action-apply <ontology> promote-employee @params.json
pltr ontology action-apply-batch <ontology> promote-employee @requests.json

# Query functions
pltr ontology query-execute <ontology> employeeStats --parameters '{"department": "Engineering"}'
```

Notes:

- `--where` takes the API's search query: `eq`, `gt`, `lt`, `isNull`,
  `containsAnyTerm`, `and`, `or`, `not` and more, with `field` and `value`.
  A mistake is a usage error (exit code 2) that names the location and the
  problem.
- `object-aggregate --group-by` takes the API's group-by objects as JSON, or
  comma-separated property names for exact groupings.
- `action-apply` exits with code 6 when Foundry reports the parameters
  invalid; `action-validate` exits with 0 and prints the validation result.
- `object-type-create` and `link-type-create` call schema endpoints that
  aren't part of the public API and may not exist on your stack (exit code
  5 when none does).

## SQL: `pltr sql`

Queries use the Spark SQL dialect and support SELECT only. Refer to datasets
by path or by RID in backticks; use single quotes in the shell so the
backticks reach pltr.

| Command | What it does |
|---|---|
| `sql execute QUERY` | Run a query, wait for it to finish and print its rows |
| `sql submit QUERY` | Start a query without waiting; print its status and query ID |
| `sql status QUERY_ID` | Get a query's status: running, succeeded, failed or canceled |
| `sql results QUERY_ID` | Print the rows of a finished query |
| `sql cancel QUERY_ID` | Cancel a running query (asks first) |
| `sql export QUERY OUTPUT_FILE` | Run a query and write its rows to a file |
| `sql wait QUERY_ID` | Wait for a submitted query to finish, then print its rows |

```bash
pltr sql execute 'SELECT region, COUNT(*) AS orders FROM `/My Space/My Project/orders` GROUP BY region'
pltr sql execute 'SELECT * FROM `<dataset-rid>` LIMIT 10' --format csv --output sample.csv
pltr sql export 'SELECT * FROM `<dataset-rid>`' orders.csv   # .json, .csv or a table

# Long-running queries
QUERY_ID=$(pltr sql submit 'SELECT * FROM `<dataset-rid>`' --format json | jq -r .queryId)
pltr sql status "$QUERY_ID"
pltr sql wait "$QUERY_ID" --timeout 600 --format json > rows.json
pltr sql cancel "$QUERY_ID" --yes
```

JSON output of `execute`, `results`, `wait` and `export` to a `.json` file
is `{"data": [...]}`, one object per row. `submit`, `status` and `cancel`
print the query status (`{"type": "running", "queryId": "..."}`). A failed or
canceled query exits with code 7, and so does `--timeout` (the query keeps
running). `sql results` exits with 6 while the query is still running.

## Orchestration: `pltr orchestration`

| Command | What it does |
|---|---|
| `orchestration builds get` | Get a build: its status, branch, jobs and timing |
| `orchestration builds create` | Start a build of datasets (or other build targets) |
| `orchestration builds cancel` | Cancel a build's unfinished jobs (asks first) |
| `orchestration builds jobs` | List the jobs of a build (paged) |
| `orchestration builds search` | [beta] Search builds by status, branch, creator and time (paged) |
| `orchestration builds get-batch` | Get several builds in one request |
| `orchestration jobs get` | [beta] Get a job: its status, build, outputs and timing |
| `orchestration jobs get-batch` | [beta] Get several jobs in one request |
| `orchestration schedules get` | [beta] Get a schedule: its trigger, build target, scope and paused state |
| `orchestration schedules create` | [beta] Create a schedule |
| `orchestration schedules replace` | [beta] Replace a schedule's definition (asks first) |
| `orchestration schedules delete` | Delete a schedule (asks first) |
| `orchestration schedules pause` | Pause a schedule |
| `orchestration schedules unpause` | Unpause a schedule |
| `orchestration schedules run` | Run a schedule now, and show the run and the build it started |
| `orchestration schedules runs` | List a schedule's recent runs (paged) |

```bash
# Search needs at least one filter
pltr orchestration builds search --status FAILED --branch master --order-by STARTED_TIME:DESC
pltr orchestration builds search --started-after 2026-01-31T00:00:00Z --all --format json

# Build a dataset (manual, upstream or connecting target) and follow it
pltr orchestration builds create '{"type": "manual", "targetRids": ["<dataset-rid>"]}' --branch master
pltr orchestration builds get <build-rid>
pltr orchestration builds jobs <build-rid>
pltr orchestration builds cancel <build-rid> --yes
pltr orchestration jobs get-batch <job-rid> <other-job-rid>

# Schedules
pltr orchestration schedules create \
  '{"target": {"type": "manual", "targetRids": ["<dataset-rid>"]}}' \
  --name "Nightly build" \
  --trigger '{"type": "time", "cronExpression": "0 2 * * *", "timeZone": "UTC"}'
pltr orchestration schedules run <schedule-rid>
pltr orchestration schedules runs <schedule-rid>
pltr orchestration schedules pause <schedule-rid>
pltr orchestration schedules delete <schedule-rid> --yes
```

`builds create --help` documents the three build target types.
`schedules replace` replaces the whole definition: fields you leave out
aren't kept.

## Data health: `pltr data-health`

Every data health endpoint is beta.

| Command | What it does |
|---|---|
| `data-health check get` | [beta] Get a check: its type, configuration and intent |
| `data-health check create` | [beta] Create a check |
| `data-health check replace` | [beta] Replace a check's configuration (asks first) |
| `data-health check delete` | [beta] Delete a check (asks first) |
| `data-health report get` | [beta] Get one report of a check: its result status and message |
| `data-health report latest` | [beta] List a check's most recent reports |

```bash
pltr data-health check create @check-config.json --intent "Monitor production builds"
pltr data-health check get <check-rid> --format json
pltr data-health report latest <check-rid> --limit 5
pltr data-health report get <check-rid> <check-report-rid>
pltr data-health check delete <check-rid> --yes
```

A check's configuration is the API's JSON: its `type` (`buildStatus`,
`nullPercentage`, `timeSinceLastUpdated`, ...) and `subject`; see
`pltr data-health check create --help`. Severities are `MODERATE` and
`CRITICAL`. The API can't list checks.

## Functions: `pltr functions`

| Command | What it does |
|---|---|
| `functions query get` | [beta] Get a query's definition by API name |
| `functions query get-by-rid` | [beta] Get a query's definition by RID |
| `functions query execute` | [beta] Execute a query by API name |
| `functions query execute-by-rid` | [beta] Execute a query given its RID |
| `functions value-type get` | [beta] Get a value type: its base type, constraints and version |

```bash
pltr functions query get myQuery
pltr functions query execute myQuery --parameters '{"limit": 10}'
pltr functions query execute myQuery --parameters @params.json --version 1.0.0 --format json
pltr functions query execute-by-rid <query-rid> --parameters '{"limit": 10}'
```

Without `--version`, the latest version is used (`--include-prerelease`
and `--latest-version-resolution` say how it's picked). `execute-by-rid`
looks the query up by RID, then executes it by API name. JSON output of
`execute` is `{"value": ...}`.

## Models: `pltr models`

The model registry (not language models). The API can't list models, so keep
the RID `model create` prints.

| Command | What it does |
|---|---|
| `models model create` | [beta] Create a model (with no versions) in the model registry |
| `models model get` | [beta] Get a model (the API returns only its RID) |
| `models version get` | [beta] Get a model version: its inputs, outputs, dependencies and source |
| `models version list` | [beta] List a model's versions (paged) |

```bash
pltr models model create "fraud-detector" --folder <folder-rid>
pltr models version list <model-rid> --all
pltr models version get <model-rid> <model-version-rid> --format json
```

## Streams: `pltr streams`

A streaming dataset has a stream per branch. Schemas use the API's format:
a `fields` list, each with a `name` and a `schema`
(`{"nullable": ..., "dataType": {"type": ...}}`), and optional
`keyFieldNames`.

| Command | What it does |
|---|---|
| `streams dataset create` | [beta] Create a streaming dataset with a stream on one branch |
| `streams stream create` | [beta] Create a branch of a streaming dataset with a new stream |
| `streams stream get` | Get the stream on a branch: its schema, view RID and settings |
| `streams stream publish` | Publish one record to a stream |
| `streams stream publish-batch` | Publish a batch of records in one request |
| `streams stream reset` | [beta] Delete all of a stream's records, optionally with new settings (asks first) |

```bash
pltr streams dataset create sensor-data --folder <folder-rid> \
  --schema '{"fields": [{"name": "id", "schema": {"nullable": false, "dataType": {"type": "long"}}}], "keyFieldNames": ["id"]}'
pltr streams stream publish <dataset-rid> --branch master --record '{"id": 123}'
pltr streams stream publish-batch <dataset-rid> --branch master --records @records.json
pltr streams stream get <dataset-rid> --branch master
pltr streams stream reset <dataset-rid> --branch master --partitions 4 --yes
```

`--type` is `LOW_LATENCY` (the default) or `HIGH_THROUGHPUT`.

## Media sets: `pltr media-sets`

Media set RIDs look like `ri.mio.main.media-set.<uuid>` and media item RIDs
like `ri.mio.main.media-item.<uuid>`.

| Command | What it does |
|---|---|
| `media-sets get` | Get a media item's metadata: path, MIME type, size and uploader |
| `media-sets get-by-path` | [beta] Look up the RID of the media item at a path |
| `media-sets create` | [beta] Open a transaction on a transactional media set |
| `media-sets commit` | [beta] Commit a transaction: its uploads become available |
| `media-sets abort` | [beta] Abort a transaction, deleting its uploads (asks first) |
| `media-sets upload` | [beta] Upload a file as a media item |
| `media-sets download` | Download a media item to a file, or to stdout with `-` |
| `media-sets reference` | [beta] Get a media item's media reference (for ontology media properties) |
| `media-sets thumbnail-calculate` | [beta] Start calculating an image's thumbnail; prints the status |
| `media-sets thumbnail-retrieve` | [beta] Download an image's thumbnail (200px wide webp) |
| `media-sets upload-temp` | Upload temporary media; prints its media reference |
| `media-sets clear` | [beta] Soft-delete the media item at a path (asks first) |

```bash
pltr media-sets get <media-set-rid> <media-item-rid>
pltr media-sets get-by-path <media-set-rid> /images/photo.jpg

# Non-transactional media sets: upload directly
pltr media-sets upload <media-set-rid> photo.jpg /images/photo.jpg

# Transactional media sets: upload in a transaction, then commit it
TXN=$(pltr media-sets create <media-set-rid> --format json | jq -r .)
pltr media-sets upload <media-set-rid> photo.jpg /images/photo.jpg "$TXN"
pltr media-sets commit <media-set-rid> "$TXN"

pltr media-sets download <media-set-rid> <media-item-rid> photo.jpg --overwrite
pltr media-sets download <media-set-rid> <media-item-rid> - --original > original.jpg
pltr media-sets thumbnail-calculate <media-set-rid> <media-item-rid>
pltr media-sets thumbnail-retrieve <media-set-rid> <media-item-rid> thumb.webp
pltr media-sets clear <media-set-rid> /images/photo.jpg --yes
```

Downloads stream to the file; without `--overwrite`, an existing file is a
usage error (exit code 2).

## Connectivity: `pltr connectivity`

The API can't list connections: Data Connection sources appear in
`pltr folder list` as `MAGRITTE_SOURCE` resources. Imports belong to a
connection, so their commands take the connection RID first.

| Command | What it does |
|---|---|
| `connectivity connection get` | Get a connection: its configuration type, worker and export settings |
| `connectivity connection create` | Create a connection with a Foundry worker runtime |
| `connectivity connection get-config` | Get a connection's configuration |
| `connectivity connection update-secrets` | Overwrite secret values on a connection (asks first) |
| `connectivity connection update-export-settings` | Replace a connection's export settings (asks first) |
| `connectivity connection upload-jdbc-drivers` | Upload custom JDBC driver JARs to a JDBC connection |
| `connectivity import file` | Create a file import from a connection into a dataset |
| `connectivity import get-file` | Get a file import |
| `connectivity import list-file` | List a connection's file imports (paged) |
| `connectivity import execute-file` | Run a file import; prints the RID of the build that runs it |
| `connectivity import table` | Create a table import from a connection into a dataset |
| `connectivity import get-table` | Get a table import |
| `connectivity import list-table` | List a connection's table imports (paged) |
| `connectivity import execute-table` | Run a table import; prints the RID of the build that runs it |

```bash
pltr connectivity connection get <connection-rid>
pltr connectivity connection get-config <connection-rid> --format json
pltr connectivity connection update-secrets <connection-rid> --secrets-file secrets.json --yes

# File import: create it, then run it
pltr connectivity import file <connection-rid> <dataset-rid> \
  --name "Daily sales" --mode SNAPSHOT --subfolder /exports \
  --filters '[{"type": "pathMatchesFilter", "regex": ".*\\.csv"}]'
pltr connectivity import execute-file <connection-rid> <file-import-rid>

# Table import from a JDBC source
pltr connectivity import table <connection-rid> <dataset-rid> \
  --name "Orders" --mode SNAPSHOT \
  --config '{"type": "jdbcImportConfig", "query": "SELECT * FROM orders"}'
pltr connectivity import list-table <connection-rid>
```

`update-secrets` reads the secrets from a JSON file so the values stay out of
your shell history; secrets not in the file keep their values.

## Language models: `pltr language-models`

The model argument of `anthropic messages`, `messages-advanced` and
`openai embeddings` is the model's API name. `enroll` calls language-model
endpoints directly (the SDK has none for it). There is no command to list
models: the SDK has no endpoint for it, and the endpoints pltr used to guess
weren't there on a live stack.

| Command | What it does |
|---|---|
| `language-models enroll` | Enroll (enable) a language model for API use |
| `language-models anthropic messages` | [beta] Send one message to an Anthropic Claude model |
| `language-models anthropic messages-advanced` | [beta] Send a full messages request to a Claude model |
| `language-models openai embeddings` | [beta] Embed texts with an OpenAI embedding model |

```bash
pltr language-models anthropic messages <model-api-name> -m "Explain RIDs" --max-tokens 300
pltr language-models anthropic messages-advanced <model-api-name> --request @request.json --format json
pltr language-models openai embeddings <model-api-name> --input '["first text", "second text"]'
```

`messages-advanced --request` takes the API's request body (camelCase:
`messages`, `maxTokens`, `system`, `tools`, `thinking` with `budgetTokens`,
...); unknown fields are a usage error. The table shows the reply and the
token counts; `--format json` prints the whole response.

## AIP agents, widgets and third-party apps

Every endpoint in these groups is beta.

| Command | What it does |
|---|---|
| `aip-agents get` | [beta] Get an agent's metadata, parameters and version |
| `aip-agents sessions list` | [beta] List your conversation sessions with an agent (paged) |
| `aip-agents sessions get` | [beta] Get a conversation session's metadata |
| `aip-agents versions list` | [beta] List an agent's published versions (paged) |
| `widgets get` | [beta] Get a widget set |
| `widgets release list` | [beta] List the releases of a widget set (paged) |
| `widgets release get` | [beta] Get a release of a widget set |
| `widgets release delete` | [beta] Delete a release of a widget set (asks first) |
| `widgets repository get` | [beta] Get a widget repository |
| `third-party-apps get` | [beta] Get a third-party application (the API returns only its RID) |

```bash
pltr aip-agents get <agent-rid> --version 1.0
pltr aip-agents sessions list <agent-rid> --all
pltr widgets release list <widget-set-rid>
pltr widgets release delete <widget-set-rid> 1.2.0 --yes
```

Widget dev mode has no curated command; use
`pltr api widgets dev-mode-settings` and `dev-mode-settings-v2`.

## Audit logs: `pltr audit`

| Command | What it does |
|---|---|
| `audit list ORGANIZATION_RID START_DATE` | List an organization's audit log files (paged) |
| `audit get ORGANIZATION_RID LOG_FILE_ID` | Download an audit log file |

```bash
pltr audit list <organization-rid> 2026-11-01 --end-date 2026-11-07 --all
pltr audit get <organization-rid> <log-file-id> --output audit.log
```

Without `--end-date` the listing has no end: paging stops at the first empty
page, and its `nextPageToken` picks up new log files later. `audit get`
never writes to a terminal: pass `--output FILE` or redirect stdout.

## Admin: `pltr admin`

User and group IDs are UUIDs: find them with `admin user search` and
`admin group search` (usernames, emails and group names are not IDs).
Organizations are RIDs (`ri.multipass..organization.<id>`).

| Command | What it does |
|---|---|
| `admin user list` | List users (paged) |
| `admin user get` | Get a user |
| `admin user current` | Get the user you are authenticated as |
| `admin user search` | Search active users by name (paged) |
| `admin user markings` | List the IDs of the markings a user can access |
| `admin user revoke-tokens` | Invalidate all of a user's tokens and browser sessions (asks first) |
| `admin user delete` | Delete a user (asks first) |
| `admin user batch-get` | Get several users in one request |
| `admin group list` | List groups (paged) |
| `admin group get` | Get a group |
| `admin group search` | Search groups by name (paged) |
| `admin group create` | Create a group |
| `admin group delete` | Delete a group (asks first) |
| `admin group batch-get` | Get several groups in one request |
| `admin role get` | [beta] Get a role: its operations and the roles it inherits |
| `admin role batch-get` | [beta] Get several roles in one request |
| `admin org get` | Get an organization |
| `admin org create` | [beta] Create an organization |
| `admin org replace` | Rename an organization, and change its description or host (asks first) |
| `admin org available-roles` | List the roles that can be assigned in an organization |
| `admin marking list` | List markings (paged) |
| `admin marking get` | Get a marking |
| `admin marking batch-get` | Get several markings in one request |
| `admin marking create` | Create a marking |
| `admin marking replace` | Rename a marking, and change its description (asks first) |

```bash
pltr admin user current
pltr admin user search jane --format json
pltr admin user get <user-id>
pltr admin group search engineering
pltr admin group create "Data Science" --organization <organization-rid> \
  --description "ML team" --attribute team=ds
pltr admin org available-roles <organization-rid>
pltr admin marking list --exclude-deleted --marking-type MANDATORY
pltr admin marking create "Project X" --category-id <category-id> \
  --role ADMINISTER:<your-user-id> --member <group-id>
pltr admin group delete <group-id> --yes
```

`org replace` and `marking replace` keep the current description (and host)
unless you pass new ones. Group members, marking members and role
assignments are managed with `pltr api admin ...` commands.

## Aliases, shell and completion

| Command | What it does |
|---|---|
| `alias add NAME COMMAND` | Create an alias (`--force` replaces an existing one) |
| `alias remove NAME` | Remove an alias (asks first) |
| `alias edit NAME COMMAND` | Change the command an alias runs |
| `alias list` | List all aliases |
| `alias show NAME` | Show the command an alias runs |
| `alias clear` | Remove every alias (asks first) |
| `alias export` | Write all aliases as a JSON object |
| `alias import INPUT_FILE` | Import aliases from a JSON file (asks before replacing existing ones) |
| `alias resolve NAME` | Show the command an alias finally runs |
| `shell` | Interactive mode: run pltr commands without typing `pltr` |
| `completion install` | Install the completion script for your shell |
| `completion show` | Print the completion script |
| `completion uninstall` | Remove the completion script `install` wrote |

```bash
pltr alias add dsg "dataset get"
pltr dsg <dataset-rid>
pltr alias list

pltr shell --profile prod
pltr shell < commands.txt        # run commands from a file

pltr completion install
eval "$(pltr completion show --shell bash)"
```

In `pltr shell`, type commands without `pltr`; `help [command]`, `exit`,
`quit`, `!command` (a system command) and aliases work too. See
[Aliases](aliases.md).
