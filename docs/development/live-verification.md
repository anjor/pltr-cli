# Live verification

pltr's tests never talk to Foundry. Service and command tests run against
`stub_foundry_http`, a real `FoundryClient` with only HTTP faked, so they prove
what pltr sends and how it reads well-formed answers, not that a real stack
answers the way the SDK says. Live verification is best-effort (#181): the
maintainer runs the smoke test, `scripts/smoke.py`, against a real stack, and
each PR says what was verified live and which assumptions couldn't be checked.

This page explains how to run the smoke test and lists every assumption the
changelog fragments (`changelog.d/*.md`) record as "Not verified live", with
the smoke check that covers it or the manual check it needs.

## Running the smoke test

### What you need

- Credentials for a stack: a pltr profile (`pltr configure configure`), or
  `FOUNDRY_HOST` with `FOUNDRY_TOKEN` (or with `FOUNDRY_CLIENT_ID` and
  `FOUNDRY_CLIENT_SECRET`). `pltr verify` should succeed.
- This repository with its dev dependencies (`uv sync --dev`). The script runs
  this checkout's pltr (`python -m pltr` with the script's own Python); to test
  an installed pltr instead, pass `--pltr pltr`.
- Some inputs (next section). A tabular dataset you can read is the most
  useful one.

### Quick start

```bash
cp scripts/smoke.example.toml smoke.toml       # git-ignored; fill in what you have
uv run python scripts/smoke.py --profile dev   # read-only checks
uv run python scripts/smoke.py --profile dev --markdown > smoke.md   # for a PR
uv run python scripts/smoke.py --profile dev \
    --allow-writes --scratch-folder ri.compass.main.folder.<uuid>    # + writes
uv run python scripts/smoke.py --list          # every check and its command
```

Progress goes to stderr, one line per check; the report goes to stdout. The
script exits with 0 when no check failed, 1 when one did, 2 for a usage or
configuration error, and 130 when you interrupt it.

### Inputs

Each check is a pltr command line with placeholders such as `<dataset.rid>`
(see `--list`). Their values come from, in order:

1. `--set KEY=VALUE` (any key), then flags such as `--dataset-rid RID` (one per
   input; see `--help`);
2. the config file: `--config FILE`, or `./smoke.toml` if it exists. It's TOML
   (or JSON with the same structure): top-level `profile` and `pltr`, and one
   table per group of inputs, e.g. `[dataset]` with `rid = "..."` for the input
   `dataset.rid`. `scripts/smoke.example.toml` documents every input;
3. what earlier checks found;
4. a few rules: `sql.query` is `` SELECT * FROM `<sql.table>` LIMIT 10 ``,
   `ontology.where` is an `eq` filter on the object's primary key, and
   `filesystem.folder_rid` defaults to the scratch folder.

A check whose input has no value is reported as skipped, with the reason
(`no input: sql.query (set sql.query or sql.table)`, or
`no input: ontology.primary_key (ontology.object-list found none)`), not as a
failure.

Found automatically when you don't set them: the ontology (the first one
`ontology list` returns), its first object type, the first object of that
type, its first outgoing link type, the dataset's branch, smallest file and
latest transaction, a build started in the last 30 days, its jobs, a schedule
(of the dataset or the build), your user ID and organization, a role ID, and
the project and space of the folder you read. Set them for a stable run: the
first object type may have no objects, for example. The text report ends with
everything the checks found ("Found by the checks"), which you can copy into
`smoke.toml`.

### Options

| Option | Effect |
|---|---|
| `--profile P` | Run every check with `--profile P` (default: pltr's own choice). |
| `--only GROUP...` | Run these groups or check IDs (`--only dataset sql.wait`), plus the checks that find their inputs. |
| `--allow-writes --scratch-folder RID` | Also run the write checks (below). |
| `--include-admin` | Also run the checks that need admin permissions (below). |
| `--markdown` | Print the report as a Markdown table, for a PR. |
| `--list` | List the checks (with `--only`: some of them) and their commands; run nothing. |
| `--pltr COMMAND` | How to run pltr, e.g. `--pltr pltr` for the one on `PATH`. |
| `--timeout SECONDS` | Time limit per command (default 600). |

### What each check verifies

Every check runs pltr in a subprocess with stdin closed, so nothing can
prompt, and with `--format json` (`dataset.read-csv` uses `--format csv`).
Besides the check's own expectations it checks the output contract
([command-contract.md](command-contract.md)):

- the exit code (some checks expect a failure, e.g. exit 2 with
  `confirmation_required`);
- on success: exactly one JSON document on stdout and only JSON Lines on
  stderr, with no error line (warnings are reported in the details);
- on failure: an empty stdout, and the structured error as the last stderr
  line, whose `exitCode` matches the process's. A failed check's details show
  its `type`, `errorName`, HTTP status, `errorCode` and message.

| Group | Checks | Needs |
|---|---|---|
| `verify` | 1 | credentials |
| `auth` | 2 | runs `pltr verify` with a made-up token and made-up OAuth client credentials, through environment variables and an empty home directory (no profile): both must exit 3 |
| `contract` | 3 | nothing: a missing folder (exit 5, or 4), an invalid RID (exit 2), a destructive command without `--yes` (exit 2) |
| `dataset` | 13 | `dataset.rid` |
| `sql` | 5 | `sql.table` or `sql.query` |
| `ontology` | 11 | nothing (found), but see Inputs |
| `action` | 1 | `action.name`, `action.parameters`; validated, never applied |
| `orchestration` | 9 | nothing (a build in the last 30 days), or `orchestration.build_rid` |
| `filesystem` | 11 | nothing for the root folder and spaces; a folder for the rest (`filesystem.folder_rid` or `--scratch-folder`) |
| `api` | 17 | one generated command per namespace: five need nothing, the others reuse the inputs above (checkpoints and language-models have none: see the checklist) |
| `functions`, `media-sets`, `aip-agents`, `widgets`, `third-party-apps`, `connectivity`, `data-health`, `models`, `streams`, `language-models` | 1 to 4 each | their inputs in `smoke.example.toml` (only `language-models` list/status need nothing) |
| `admin`, `audit` | 8 | `--include-admin` |
| `write` | 39 | `--allow-writes --scratch-folder RID` |
| `admin` (no-op replaces) | 9 | `--include-admin --allow-writes` and `admin.replace_*` |

Run `uv run python scripts/smoke.py --list` for every check with its exact
command, or `--list --markdown` for a table.

### The write pass

`--allow-writes` needs `--scratch-folder RID`: a folder or project (not the
root folder) where you may create things. Without `--allow-writes` no write
check runs, even with a scratch folder (then the folder is only read). The
write checks create `pltr-smoke-<date>-<time>` in the scratch folder and, in
it, a dataset, uploads files (one file, one into an open transaction, one with
`--transaction-type`, a directory), downloads them again and compares the
bytes, commits and aborts transactions, applies and sets a schema and reads the
CSV files back as a table, creates, lists and deletes a branch (first checking
that deleting without `--yes` exits 2), deletes a file, copies the dataset with
`pltr cp`, trashes and restores the dataset, and creates a streaming dataset
and publishes a record. With `writes.space_rid` it also creates a project and
moves it to the trash. `write.sql-cancel-finished` cancels the SQL checks' own
query after it has finished.

Everything is created inside the run's folder or project, and the cleanup
checks move the copy, the streaming dataset, the project and finally the
run's folder to the trash; they run even after earlier failures and after
Ctrl-C (a second Ctrl-C stops at once). Nothing is ever permanently deleted:
empty the trash yourself. If a cleanup check fails, the report lists what was
left behind, with the command that trashes it.

The write checks only ever change what the run created: the scratch folder and
`writes.space_rid` are only used as parents (a test enforces this).

### Admin checks

`--include-admin` adds read-only checks that need admin permissions: user
search (it must find you by your username), users, groups, markings (with
`--exclude-deleted --marking-type MANDATORY`), your organization (or
`admin.organization_rid`), its assignable roles, `admin role get` with one of
those role IDs, and the audit log files of the last week.

With `--include-admin --allow-writes` and the `admin.replace_space_rid`,
`admin.replace_organization_rid` or `admin.replace_marking_id` inputs, the
script reads that space, organization or marking, replaces it with its current
name (`pltr space update --name`, `pltr admin org replace`, `pltr admin marking
replace`), and checks that its other fields didn't change. pltr sends back the
values you don't pass, so nothing should change; if something does, the
details show the old values to restore. Use test objects. The script never
creates spaces, organizations, groups or markings, and never deletes them.

### Reading the report

Each check is `PASS`, `FAIL` or `SKIP`, with its time and details: what it saw
for a pass (`5 items, more pages`, `validation.result INVALID`, `unchanged:
name, description, host`), the reason for a skip, and for a failure the exit
code and structured error, or what was wrong with the output (`unexpected
output: ...`, `contract: stdout is not exactly one JSON document ...`).

The text report then repeats each failed check's full command line and error
JSON, lists what the checks found, and says which checks didn't run for lack
of `--allow-writes` or `--include-admin`. `--markdown` prints the table for a
PR: commands show inputs as `<key>`, without your RIDs, but read the details
before you paste them, since error messages can name RIDs.

To look into a failure, run that check alone (`--only dataset.read-csv`; the
checks that find its inputs run too), or run the command from the "Failed
checks" section yourself, with `PLTR_DEBUG=1` for a traceback. Not every
failure is a pltr bug: a beta endpoint may not be enabled on the stack, or your
user may lack a permission (exit 4).

### Working on the smoke test

The checks are the `CHECKS` table in `scripts/smoke.py`: an ID (`group.name`),
the command after `pltr` with `{key}` placeholders, a sentence about what it
verifies, validators for the output (`paged()`, `equals("rid", "{dataset.rid}")`,
...), `capture` for the values later checks need, and flags (`write`, `admin`,
`cleanup`, expected exit codes and error types). A check runs after the checks
that capture its inputs.

- `tests/test_smoke_script.py` tests the script with a fake runner: config
  parsing, skips, the contract evaluation, the reports, the write-pass guard,
  the safety rules of the table, and that every check's command line parses
  against the real CLI.
- `tests/test_smoke_script_stubbed.py` runs every check except `auth` through
  the real CLI in-process, against a small stateful fake of the endpoints they
  call. A new check needs a route there.

## Checklist: assumptions not verified live

Every assumption recorded as "not verified live" while this release was
built, grouped by area. The labels (a1 to e1) name the work items the notes
came from; the notes themselves were folded into `CHANGELOG.md`. **Smoke**
names the checks that verify it (and what to look at); **Manual** says what
to try by hand. "Partly" means the smoke check covers the common case only.

### Output contract, errors and authentication (a1, a3)

- **`Space.replace` resets optional fields it isn't sent; sending the current
  `defaultRoleSetId`/`usageAccountRid` back is accepted.** Smoke:
  `admin.space-before`, `admin.space-update-unchanged`, `admin.space-after`
  (`--include-admin --allow-writes`, `admin.replace_space_rid`) verify the
  second half. Manual for the first: on a test space, `pltr api filesystem
  space replace <space> --display-name <name>` without the other fields, then
  `pltr space get <space>`.
- **`folder list ri.compass.main.folder.0` lists the root folder.** Smoke:
  `filesystem.root-folder-list`.
- **A failed OAuth token request (`SDKInternalError` caused by an HTTP error
  from `.../oauth2/token`) exits 3.** Smoke: `auth.invalid-oauth-client`.
- **Typed SDK errors drop `errorCode`; pltr derives it from the HTTP status.**
  Partly: `contract.not-found` shows the `errorCode` pltr reports for a 404.
  Manual: compare a few errors (403, 409, 422) with the raw response, e.g.
  `curl -s -H "Authorization: Bearer $TOKEN" https://$HOST/api/v2/filesystem/folders/ri.compass.main.folder.00000000-0000-4000-8000-000000000000`.
- **`admin.User.get_current()` works for user tokens and OAuth clients with
  `api:admin-read`, and fails with 403 `GetCurrentUserPermissionDenied`
  without that scope.** Smoke: `verify` (with the credentials you run with).
  Manual: `pltr verify --format json` with an OAuth client without
  `api:admin-read`: exit 4, `permission_denied`.
- **Direct-HTTP calls get their OAuth token through the SDK's
  `ConfidentialClientAuth`.** Manual: run the smoke test with an OAuth profile
  or OAuth environment variables; `language-models.list` and
  `write.schema-apply` are direct-HTTP commands.
- **A client-credentials token request without scopes gets every scope granted
  to the client.** Manual: an OAuth profile without scopes; run the smoke test
  with it.
- **The keyring time limit (`PLTR_KEYRING_TIMEOUT`) stops a blocking keyring.**
  Manual: on macOS over SSH (locked Keychain), `pltr verify --profile <p>`
  should fail with exit 3 after 30 seconds instead of hanging.

The SDK-call guardrail (a2) made no live assumptions: it only reads
`foundry-platform-sdk` signatures.

### Datasets (b1)

- **`dataset schema apply` calls internal endpoints whose shapes are
  assumed.** Smoke: `write.schema-apply` (and `write.schema-get` after it).
- **`branches create` from a parent branch whose latest transaction is OPEN**
  fails with `TransactionNotCommitted`, which pltr explains (commit or abort it,
  or pass `--transaction-rid`). Manual: `pltr dataset transactions start <ds>`,
  then `pltr dataset branches create <ds> b2` (expect exit 6 and the hint), then
  `pltr dataset transactions abort <ds> <txn> --yes`.
- **`views remove-datasets`/`replace-datasets` match backing datasets sent with
  an empty `stopPropagatingMarkingIds`.** Manual: `pltr dataset views create v1
  --parent-folder <folder> --backing-dataset <ds1> --backing-dataset <ds2>`,
  then `pltr dataset views remove-datasets <view> <ds2> --yes` and `pltr
  dataset views get <view>`.
- **`files upload FILE --transaction-type` without `--branch`** now opens a
  transaction on the default branch, uploads into it and commits; `SNAPSHOT`
  asks for confirmation. Smoke: `write.files-upload-append`.
- **`schema set --dataframe-reader CSV` makes Foundry read uploaded CSV
  files.** Smoke: `write.schema-set`, `write.read-table` (it needs the columns
  `id`, `name`, `value`, and notes header rows read as data).
- **`pltr cp` cleanup trashes a partly copied dataset with
  `Resource.delete`.** Partly: `write.trash-dataset` shows that
  `Resource.delete` trashes datasets. Manual: make a copy fail midway (e.g.
  into a folder where you can't write files) and check that nothing is left.
- **Arrow decoding in `dataset preview` for every type, and `read_table`'s row
  limit.** Partly: `dataset.read-json` and `dataset.read-csv` decode the types
  of your `dataset.rid`; point it at a dataset with DECIMAL, MAP, STRUCT and
  BINARY columns. Manual: `pltr dataset preview <csv-dataset-rid> --limit
  1000000` on a dataset that isn't stored as Parquet.

### Ontology (b2)

- **The schema endpoints of `object-type-create`/`link-type-create`** (the
  first two are requested at the host root and probably return 404). Manual
  only, since the smoke test never changes an ontology: on a test ontology,
  `pltr ontology object-type-create <ontology> --api-name SmokeType
  --display-name "Smoke type" --primary-key id --backing-dataset <ds>`, and
  see which endpoint answers (stderr) or whether it fails.
- **`object-search` sends `select: []` to get every property.** Smoke:
  `ontology.object-search` (fails if the objects come back with only `__`
  fields).
- **`action-apply` reports INVALID parameters with a 200 (exit 6), or Foundry
  answers 400 `ActionValidationFailed` (also exit 6).** Manual (applying
  changes data): `pltr ontology action-apply <ontology> <action> '<invalid
  parameters>'` on a test ontology; both forms exit 6. `action.validate` covers
  the VALIDATE_ONLY call.
- **`object-count` works with `preview=true`.** Smoke: `ontology.object-count`.
- **`--return-edits`, the attribution header, `--default-load-level`,
  `--derived-properties`, `--scenario-rid`, `--transaction-id` and
  `--include-datasources` have the effect the SDK describes.** Partly:
  `ontology.object-type-get` sends `--include-datasources` and notes the
  number of datasources ("no datasources in the output" means it had no
  effect). Manual for the rest, e.g. `pltr ontology object-search <ontology>
  <type> --default-load-level noLoadLevel`.
- **What `excludedItems` means in aggregate responses.** Manual: an aggregation
  over a large object type with `--accuracy ALLOW_APPROXIMATE`.

### Filesystem (b3)

- **`project delete` works because `Resource.delete` accepts project RIDs.**
  Smoke: `write.project-delete`, `write.project-trashed` (needs
  `writes.space_rid`).
- **`project list` takes the children of a space to be its projects
  (`Resource`s whose `projectRid` is their own RID).** Smoke:
  `filesystem.project-list` (0 items for a space with projects means the
  assumption is wrong).
- **`project create` grants `compass:manage` to the owner by default.** Smoke:
  `write.project-create` (in the space you give; a space with a custom role set
  needs `--owner-role`).
- **`resource list` and `resource search` without `--folder-rid` list the root
  folder.** Smoke: `filesystem.resource-list-root`. Manual: `pltr resource
  search <text> --max-folders 50`.
- **`resource-role list --include-inherited`.** Smoke:
  `filesystem.resource-roles`; compare with the output without the flag.
- **The requests of a dataset copy with `pltr cp`.** Smoke: `write.cp`.

### Admin (b4)

- **Request and response shapes of the admin commands.** Smoke: the `admin`
  and `audit` checks (`--include-admin`).
- **`Organization.replace` and `Marking.replace` clear the optional fields
  they aren't sent (the reason pltr reads first).** Smoke: `admin.org-*` and
  `admin.marking-*` show that pltr's replace keeps them. Manual for the
  premise: `pltr api admin organization replace <org> --name <name>` on a test
  organization, then `pltr admin org get <org>`.
- **`--description ''` stores an empty description.** Manual: `pltr admin org
  replace <test-org-rid> <name> --description '' --yes`.
- **`Group.create` with empty attributes, `Marking.create` with no
  `--member`.** Manual (the smoke test never creates groups or markings).
- **Role IDs from `admin org available-roles` work with `admin role get`.**
  Smoke: `admin.role-get`.
- **`--include-deleted` is the default; search is a case-insensitive prefix
  search that leaves out deleted users.** Partly: `admin.marking-list` (no
  deleted marking with `--exclude-deleted`), `admin.user-search` (finds you by
  your username). Manual: compare `pltr admin marking list --all` with
  `--exclude-deleted`, and search with an upper-case prefix.

### SQL, streams and media sets (b5)

- **SQL results decode from Arrow IPC.** Smoke: `sql.execute`, `sql.wait`,
  `sql.results`.
- **The CSV fallback for queries run with `serializationFormat` CSV
  elsewhere.** Manual: `pltr api sql-queries sql-query execute --query
  '<query>' --serialization-format CSV --format json`, then `pltr sql results
  <queryId>`.
- **`getResults` waits about a minute for a running query, then fails with
  `QueryRunning` (exit 6).** Manual: `pltr sql results` right after
  `pltr sql submit` of a slow query.
- **Canceling a finished query changes nothing.** Smoke:
  `write.sql-cancel-finished`.
- **The stream schema format of the help (`fields`, `keyFieldNames`).**
  Smoke: `write.stream-create`.
- **High-scale publish endpoints at `<host>/api/v2/highScale/...`.** Smoke:
  `write.stream-publish`.
- **`media-sets get-by-path` answers 200 without `mediaItemRid` when no item
  exists (pltr warns, exit 0; a 404 would exit 5).** Smoke:
  `media-sets.get-by-missing-path` passes either way; a warning in its details
  means 200, `exit 5` means 404.
- **`media-sets create` returns the transaction ID as a bare JSON string; an
  uncalculated thumbnail is an empty 200; `thumbnail-calculate` can be called
  again to check progress; `upload` works without a transaction on a
  non-transactional media set; `clear` soft-deletes the item at a path.**
  Manual, on a test media set: `pltr media-sets create <set>`, `pltr
  media-sets upload <set> <file> <path> [<transaction>]`, `pltr media-sets
  thumbnail-calculate <set> <item>` twice, `pltr media-sets thumbnail-retrieve
  <set> <item> out.png`, `pltr media-sets clear <set> <path> --yes`, then
  `pltr media-sets get-by-path <set> <path>`.

### Builds, schedules, functions and models (b6)

- **`builds search` time filters and `--created-by` value formats.** Smoke:
  `orchestration.builds-search` (`--started-after`),
  `orchestration.builds-search-mine` (`--created-by`; fails if it returns
  someone else's build).
- **`schedules replace` replaces the whole schedule (fields you don't pass
  aren't kept).** Manual, on a test schedule: `pltr orchestration schedules
  replace <schedule> '<action JSON>' --yes`, then `pltr orchestration
  schedules get <schedule>`.
- **`functions query execute-by-rid` runs the version `Query.get_by_rid`
  resolved, by API name.** Smoke: `functions.query-execute-by-rid` (compare
  with `functions.query-execute`).
- **The RID formats in the help (`ri.foundry.main.build.<id>`,
  `ri.foundry.main.job.<id>`, `ri.scheduler.main.schedule.<id>`,
  `ri.data-health.main.check.<id>`).** Smoke: the text report's "Found by the
  checks" lists the build, job and schedule RIDs found; check RIDs come from
  your `data_health.check_rid`.

### Connectivity, language models and audit (b7)

- **`language-models list`, `status` and `enroll` call endpoints outside the
  SDK, with assumed response shapes.** Smoke: `language-models.list`,
  `language-models.status`. Manual for `enroll` (it changes the enrollment):
  `pltr language-models enroll <model>` on a model you mean to enroll.
- **The model argument of `anthropic messages` and `openai embeddings` is the
  model's API name; RIDs may or may not work.** Smoke (API name):
  `language-models.anthropic-messages`, `language-models.openai-embeddings`.
  Manual: the same with a model RID.
- **Whether `encodingFormat: BASE64` embeddings decode with the SDK.** The
  curated command refuses `--encoding base64` (the SDK's response model only
  holds floats). Manual: `pltr api language-models open-ai-model embeddings
  <model> --input x --encoding-format BASE64 --format json`; expected exit 7,
  `invalid_response`. If it succeeds, the curated choice can come back.
- **Data Connection source RIDs look like `ri.magritte..source.<id>` and show
  up in `pltr folder list` as `MAGRITTE_SOURCE` resources.** Partly:
  `connectivity.connection-get` with your `connectivity.connection_rid`.
  Manual: `pltr folder list <folder-rid>` for a folder with a source.
- **`audit list --page-token` sends the start date with the token.** Manual:
  `pltr audit list <org> <date> --max-pages 2`.
- **`LogFile.list` without an end date returns a `nextPageToken` on every
  page.** Smoke: `audit.list` (its details say "more pages" when a token came
  back).
- **The format of audit log files.** Manual: `pltr audit get <org> <log-file-id>
  --output log.bin`, then `file log.bin`.

### Widgets, AIP Agents, third-party applications and completion (b8)

- **The example RID formats in the help.** Manual: compare with the RIDs you
  use as inputs.
- **The Widgets, AIP Agents and Third Party Applications endpoints accept
  `preview=true`.** Smoke: `aip-agents.*`, `widgets.*`, `third-party-apps.get`,
  `api.aip-agents`, `api.widgets`, `api.third-party-applications`.
- **`widgets release list --branch` and the response shapes.** Smoke
  (shapes): `widgets.release-list`. Manual: `pltr widgets release list <set>
  --branch <branch>`.
- **Completion scripts work in zsh and fish (verified end to end in bash
  only).** Manual: `pltr completion install --shell zsh` (and `fish`), open a
  new shell, type `pltr da<TAB>`.

### Generated `pltr api` commands (c1)

- **Generated commands against a live stack.** Smoke: the `api` checks, one per
  namespace except checkpoints (`pltr api checkpoints record search` needs a
  filter; manual) and language-models (its endpoints are covered by the
  curated `language-models` checks).
- **Streaming endpoints write the bytes as they arrive (formats unverified).**
  Manual: `pltr api ontologies time-series-property-v2 stream-points
  <ontology> <object-type> <primary-key> <property> --output points.bin`.
- **`--max-pages`/`--all` resend the other arguments with the `nextPageToken`.**
  Smoke: `api.filesystem` (`--page-size 1 --max-pages 2`; "2 items" means
  the second page was fetched).
- **A left-out required list parameter is sent as `[]` (e.g. `select`).**
  Smoke: `api.ontologies-search`.
- **`ontologies attachment upload` sends `Content-Type: */*` whatever
  `--content-type` says.** Manual: upload an attachment and check its MIME
  type.

### Command manifest and agent skill (d1)

- **`pltr commands` makes no Foundry call**: nothing to verify live.
- **The agent skill's workflow payloads.** The skill's commands and flags are
  checked against the CLI, but not its payloads. The ontology search filter
  (`{"type": "eq", "field": ..., "value": ...}`, `and`, `gt`): Smoke:
  `ontology.object-search` (set `ontology.where`). SQL that refers to a
  dataset by RID or path in backticks: Smoke: `sql.execute`. The build
  target JSON: Manual: `pltr orchestration builds create '{"type": "manual",
  "targetRids": ["<dataset-rid>"]}' --branch master` on a dataset you may
  build. Role IDs such as `compass:manage`: Manual: `pltr resource-role list
  <resource-rid>` shows the role IDs in use on your stack.

### Cleanup: `pltr cp` schemas, errors, downloads (e1)

- **`pltr cp`'s dataset sequence**: create, list the files, start a SNAPSHOT
  transaction, download, upload into it, commit, read the source's schema on
  `--branch`, and put it with the branch and the committed transaction.
  Partly: `write.cp` copies the scratch dataset after `write.schema-set`.
  Manual: `pltr cp <dataset-rid> <folder-rid>`, then
  `pltr dataset schema get <copy-rid>` and `pltr dataset preview <copy-rid>`.
- **`getSchema` answers `SchemaNotFound` (not `DatasetViewNotFound`) for a
  source that has files but no schema**, so the copy is made without one.
  Manual: upload a file to a new dataset without setting a schema, then
  `pltr cp` it: it should exit 0 with a copy and no schema.
- **`putSchema` with `dataframeReader: CSV` makes Foundry read copied CSV
  files, and the `PARQUET` default fits datasets built by transforms.**
  Partly: `write.cp` copies CSV files. Manual: `pltr cp` a dataset built by a
  transform, then `pltr dataset preview <copy-rid>`.
- **Decode failures are told apart from argument mistakes** by where the
  pydantic error was raised; checked against foundry-platform-sdk 1.111.0 and
  pydantic 2.11 only. Smoke: `contract.invalid-rid` (an argument mistake still
  exits 2). A response that doesn't match the SDK's model can't be provoked on
  demand: after an SDK or pydantic upgrade, look out for `invalid_response`
  errors (exit 7) where a usage error is expected, and the reverse.
- **`pltr cp --branch X` for a branch other than the new dataset's default
  branch.** `Dataset.create` makes only the default branch, so pltr creates `X`
  on the copy (with no transaction) before the SNAPSHOT transaction. Assumes such
  a branch accepts the transaction and then `putSchema`. Manual:
  `pltr cp <dataset-rid> <folder-rid> --branch <other-branch>`, then
  `pltr dataset files list <copy-rid> --branch <other-branch>`.
- **`pltr cp -r` refuses a target inside the source folder**, using
  `Resource.path` (assumed to be the `/`-joined display-name path). Manual:
  `pltr cp -r <folder-rid> <subfolder-rid>` should exit 2 before creating
  anything; `pltr cp -r <folder-rid> <sibling-rid>` should copy.

### The smoke test itself (d2)

The smoke script has run only against fakes, so a failing check can be the
script's fault. It assumes that:

- a made-up folder RID answers 404 (403 is accepted too), a made-up token 401,
  and made-up OAuth client credentials fail the token request: `contract.not-found`,
  `auth.invalid-token`, `auth.invalid-oauth-client`;
- `resource get`, `folder get` and `project get` return a trashed resource
  with its `trashStatus` (`DIRECTLY_TRASHED`) rather than 404:
  `write.dataset-trashed`;
- CSV files with a schema from `schema set --from-csv --dataframe-reader CSV`
  read back as rows with the CSV's columns: `write.read-table`;
- `pltr cp` of the scratch dataset prints the copy as `data[0]`: `write.cp`;
- a streaming dataset can be created in the scratch folder (streaming may not
  be enabled on every stack): `write.stream-create`;
- `builds search --started-after <30 days ago>` finds a build on an active
  stack: `orchestration.builds-search` (otherwise the build checks skip unless
  `orchestration.build_rid` is set);
- `admin user search <your username>` finds you (prefix search):
  `admin.user-search`.
