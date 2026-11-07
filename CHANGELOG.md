# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While pltr is 0.x, a minor release can contain breaking changes; they are
listed under "Breaking changes" or marked **Breaking**.

Entries for 0.5.0 to 0.16.0 were written after the fact from the git history
and pull requests. Numbers in parentheses are pull requests or issues.

## [Unreleased]

This release puts every pltr command on one set of rules for output, errors
and confirmations, fixes about 40 commands that could never succeed, and adds
`pltr api`, a command for every method of the Foundry Platform SDK. It changes
the JSON output, where messages are printed, the exit codes and some arguments
and flags, so scripts that call pltr need updating: read "Breaking changes"
first. Renamed and removed flags keep working for one release, as hidden
aliases that print a deprecation warning (see "Deprecated").

pltr now requires foundry-platform-sdk 1.111.0 or later (#179).

### Breaking changes

- **JSON output is the Foundry SDK's own serialization.** `--format json`
  prints the API's response as foundry-platform-sdk serializes it: Foundry API
  field names (camelCase, as in Foundry's REST docs), no null fields and no
  fields pltr made up. Lists print `{"data": [...], "nextPageToken": "..."}`,
  with `nextPageToken` only when more pages exist. A command with no result
  prints `null`. This replaces pltr's own snake_case keys in every command:
  for example, read `.rid` instead of `.transaction_rid`, and `.nextPageToken`
  instead of `.pagination.next_page_token`.
- **stdout carries only data.** Status lines, progress, warnings, prompts and
  errors go to stderr. With `--format json`, stderr carries only JSON Lines:
  warnings are `{"type": "warning", "message": ...}`, and a failure ends with
  one structured error (`type`, `message`, `exitCode`, and for API errors
  `statusCode`, `errorCode`, `errorName`, `errorInstanceId`, `parameters`).
- **Exit codes are documented.** Every error used to exit with 1. Now: 0
  success; 1 unexpected error, or "no" at a confirmation prompt; 2 usage error
  (bad arguments, invalid JSON input, an invalid RID, or `--yes` needed); 3
  authentication; 4 permission denied (HTTP 403); 5 not found (404); 6
  validation error (400, 422); 7 other API or network errors (409, 413, 429,
  5xx, timeouts, connection errors, or a response pltr can't read).
- **Destructive commands ask first, and `--yes`/`-y` skips the question,
  everywhere.** Deletes, removes, revokes, resets, cancels, aborts, replaces,
  clears and schema changes ask on stderr; several asked nothing before (see
  Changed). Nothing prompts when stdin is not a terminal: without `--yes`
  such a command exits with code 2 and changes nothing. Answering "no" exits
  with 1; several commands exited with 0. `--confirm` and `--force`, where
  they meant "don't ask", are hidden aliases of `--yes` for one release.
- **`-f` means `--format`.** It used to mean `--force` on `configure delete`,
  `resource delete`, `resource permanently-delete` and
  `data-health check delete`. Commands where `-f` was already something else
  keep it (`--folder`, `--folder-rid`, and `--force` on `alias add`).
- **Beta endpoints work without `--preview`.** Commands that call a beta
  Foundry endpoint send `preview=true` themselves, and their help starts with
  `[beta]`. Commands that call GA endpoints no longer send `preview`, so the
  SDK's warning is gone. `--preview` flags are hidden no-ops for one release.
- **List commands fetch one page by default.** They take `--page-size`,
  `--page-token`, `--max-pages N` and `--all`. Several fetched every page.
  Without `--page-size` the API's default page size is used, not pltr's
  `page_size` setting.
- **Table and CSV columns changed** in most commands: every column reads a
  field the API returns. Many old columns read fields that don't exist and
  were always empty or `N/A`. `--format` accepts only `table`, `json` and
  `csv`; other values fell back to a table.
- **Removed commands.** None of them could work with the SDK:
  `connectivity connection list`, `dataset views list`,
  `resource get-metadata`, `resource-role get-principal-roles`,
  `resource-role get-available-roles`, and `widgets dev-mode get`, `enable`,
  `disable` and `pause`. See Removed for what to use instead.
- **New arguments** for commands that never worked as documented:
  `connectivity import` commands take the connection RID first;
  `data-health report get` takes the check RID and the report RID;
  `dataset views create` takes `VIEW_NAME --parent-folder --backing-dataset`;
  `ontology object-search` filters with `--where` (`--query` is gone);
  `ontology object-aggregate` takes `--aggregation`; `resource-role grant` and
  `revoke` take `--principal-id` (or `--everyone`) and `--role`;
  `orchestration builds search` needs a filter.
- **`pltr cp` copies schemas, and fails if it can't.** With `--schema` (the
  default), a dataset copy that can't read the source's schema or put it on
  the copy moves the partial copy to the trash and exits with the error. It
  used to warn and exit 0, leaving a copy without a schema (in fact cp never
  copied a schema; see Fixed). A source with no schema is still copied
  without one; `--no-schema` copies only the files.
- **Authentication.** `FOUNDRY_HOST` with `FOUNDRY_TOKEN`, or with
  `FOUNDRY_CLIENT_ID` and `FOUNDRY_CLIENT_SECRET`, now works without a stored
  profile, keyring or configuration directory (#190, #144). pltr uses the
  first of: `--profile`, `PLTR_PROFILE`, the default profile, the environment
  variables. A variable never overrides, or fills gaps in, a stored profile.
  `PLTR_PROFILE` naming a profile that doesn't exist is an error; it fell
  back to the default profile. `pltr verify` calls the SDK's
  `User.get_current`, so OAuth clients need the `api:admin-read` scope, and it
  reports which credentials it used.

Also new: **`pltr api`**, a generated command for every callable method of the
SDK's V2 client (390 commands for foundry-platform-sdk 1.111.0), and
**`pltr commands`**, a machine-readable manifest of every command that agents
can search. See Added.

### Added

- **`pltr api <namespace> <resource> [<sub-resource>...] <method>`**: one
  command for every callable method of the Foundry Platform SDK's V2 client,
  generated from the SDK: 390 commands in 18 namespaces for
  foundry-platform-sdk 1.111.0 (#186). It covers build and job status (#145).
  See `docs/api-commands.md`.
  - Path parameters are arguments, other parameters are options. Models,
    unions and dicts take JSON inline, as `@file.json` or as `@-` (stdin);
    `bytes` bodies take `--body FILE` or `--body -`.
  - The commands follow the same output, error and confirmation rules as the
    curated ones and have the same shared options. A paged command prints one
    page exactly as the API returns it (with fields such as `totalCount`);
    `--max-pages` and `--all` print the merged items in the paged shape.
  - 203 beta commands are labeled `[beta]` and send `preview=true`, if the
    installed SDK method still takes it. 58 destructive commands, an explicit
    reviewed list, ask for confirmation. 20 commands with binary responses
    write to `--output FILE`, or to stdout when it isn't a terminal.
  - The commands load lazily, so `pltr --help` stays fast.
  - Four SDK methods have no command: `functions.Query.streaming_execute` and
    `streaming_execute_events` (server-sent events), and `MediaSet.tile` and
    `ModelStudio.ConfigVersion.get`, which foundry-platform-sdk 1.111.0 can't
    call (it fails to URL-quote their integer path parameters).
- **`pltr commands`**: a machine-readable manifest of every command, curated
  and generated, so agents can find the right command without reading every
  `--help` page (#188). These commands make no Foundry call.
  - `pltr commands list [PATH...]` lists every command, or those under a path
    such as `api datasets`. With `--format json` it prints the whole manifest,
    `{"pltrVersion", "sdkVersion", "groups", "commands"}`, deterministically:
    sorted, no timestamps, the same on every OS, terminal and Python version.
    `sdkVersion` is the SDK version `pltr api` was generated from.
  - `pltr commands search <text...>` ranks commands by path, SDK method,
    description and help; curated commands rank above generated ones that
    match as well. `--limit/-n` (default 10). JSON:
    `{"data": [...], "totalCount": N}`.
  - `pltr commands show <command path...>` prints one command's entry. It
    accepts `dataset get`, `"dataset get"` or `"pltr dataset get"`; an unknown
    path is a usage error with suggestions.
  - Each entry has `path`, `usage`, `description`, `beta`, `destructive`,
    `paged`, `generated`, `local`, `hidden`, `outputFormats`, `sdkMethods`,
    `httpEndpoints` (direct-HTTP commands only), `arguments`, `options`
    (hidden deprecated aliases left out) and `help`.
- The README has a section on using pltr from agents (headless auth, finding
  commands with `pltr commands`, JSON output, exit codes, `--yes`).
- Environment-variable authentication, as described under Breaking changes.
  `FOUNDRY_HOSTNAME`, the SDK's name for the host, is accepted when
  `FOUNDRY_HOST` isn't set. Hosts work with or without `https://`. If both a
  token and client credentials are set, the token wins.
- `PLTR_FORMAT=table|json|csv` sets the default `--format` of every command.
- `PLTR_DEBUG=1` prints the Python traceback of an unexpected error.
- `PLTR_KEYRING_TIMEOUT`: how many seconds to wait for the system keyring
  (default 30; `0` waits indefinitely).
- The error type `invalid_response` (exit code 7): the API's response doesn't
  match the SDK's model or isn't JSON, so pltr can't read it. Upgrade pltr; a
  retry won't help. For a response that doesn't match, the message names the
  model and the fields.
- `pltr verify --format table|json|csv` and `--output`. JSON is
  `{"authSource": {...}, "user": {...}}`: where the credentials came from
  (profile or environment, and how it was selected), the auth type and host,
  and the SDK's `User`.
- New commands:
  - `connectivity import execute-file` and `execute-table`: run an import and
    print the RID of the build that runs it.
  - `data-health report latest CHECK_RID [--limit N]`: a check's most recent
    reports, the way to find the report RIDs that `report get` needs.
  - `media-sets clear MEDIA_SET_RID MEDIA_ITEM_PATH` [beta]: soft-delete the
    media item at a path (#170).
  - `ontology action-apply-batch ONTOLOGY ACTION REQUESTS`: apply several
    actions of one action type in one request.
- New options, by area:
  - **dataset**: `files upload` uploads a directory recursively, in one
    transaction that pltr opens and commits (or aborts if an upload fails),
    with `--path` and `--transaction-type`; `files get --recursive/-r`, and
    `-` as the output path for stdout (downloads stream and are written
    atomically); `files list --path-prefix`; `--start-transaction-rid` and
    `--end-transaction-rid` on `files list`, `get` and `info`;
    `files delete --transaction-rid`; `preview --column` and `--branch`;
    `schema get --branch`, `--transaction-rid` and `--version-id`;
    `schema set --dataframe-reader`, and `--json` accepts `@file.json`, the
    API's `{"fieldSchemaList": [...]}` and the output of `schema get`;
    `branches create --transaction-rid`; `views add-primary-key --latest-wins`
    and `--deletion-column`; `--branch` on every `views` command and
    `DATASET_RID@BRANCH` for backing datasets; `jobs list --order-by` and
    `--ascending`; `schedules list --branch`.
  - **ontology**: `object-search --where`, `--order-by`,
    `--default-load-level`, `--derived-properties/--no-derived-properties`;
    `object-aggregate --aggregation`, `--where`, `--accuracy`, `--branch`, and
    `--group-by` as JSON or as property names; `object-get --scenario-rid`,
    `--transaction-id`, `--branch/-b` and `--derived-properties`;
    `object-list` and `object-linked --branch/-b` and `--derived-properties`;
    `object-type-list` and `object-type-get --include-datasources`;
    `action-apply --return-edits`, `--attribution` and `--scenario-rid`. JSON
    inputs accept `@file.json` and `@-`, and are checked against the SDK's
    models before anything is sent. The ontology argument accepts the
    ontology's API name as well as its RID.
  - **folder, space, project, resource, resource-role**:
    `space create --default-role-set-id`, `--file-system-id` and
    `--usage-account-rid`; `space update --default-role-set-id` and
    `--usage-account-rid`; `project create --owner-role` and `--default-role`;
    `project create-from-template --default-role`; `resource-role grant` and
    `revoke --everyone`; `resource-role list --include-inherited`, and
    `--principal-type EVERYONE`; `resource search --limit` and
    `--max-folders`; `resource batch-get` and `batch-get-by-path` warn about
    RIDs and paths they couldn't get.
  - **admin**: `group create --organization` (required) and `--attribute`;
    `marking create --role ROLE:PRINCIPAL_ID` and `--member`;
    `marking list --include-deleted/--exclude-deleted` and `--marking-type`;
    `org create --description` and `--host`; `org replace --host`.
  - **orchestration**: `builds search --where`, `--status`, `--branch`,
    `--created-by`, `--started-after`, `--started-before`, `--finished-after`,
    `--finished-before` and `--order-by`; `builds create --fallback-branch`
    and `--retry-count`; `schedules create` and `replace --scope-mode`; JSON
    arguments accept `@file.json`; `builds get-batch` and `jobs get-batch`
    accept RIDs separated by spaces.
  - **functions**: `--include-prerelease` on the `query` commands, and
    `--latest-version-resolution` on `query get` and `query execute`.
  - **models**: `version list --branch`.
  - **streams and media-sets**: `streams stream reset --schema`,
    `--partitions`, `--type` and `--compressed/--no-compressed` (new stream
    settings; the others are kept); `--no-compressed` on the create commands;
    `@-` for JSON inputs; `media-sets download` and `thumbnail-retrieve`
    accept `-` for stdout; `media-sets upload --branch`, and its
    TRANSACTION_ID is optional (only transactional media sets need it).
  - **language-models**: `anthropic messages-advanced` accepts
    `outputConfig`.
  - **widgets**: `release list --branch`.
  - **local commands**: `configure configure --yes`; `configure configure`
    infers `--auth-type` from the credentials given;
    `configure list-profiles --format json`
    (`{"data": [{"name", "default"}]}`); `alias list`, `show` and `resolve`
    print tables, JSON or CSV; `pltr shell` expands aliases, completes alias
    names, accepts `help [command]`, `exit`/`quit`, `!command` and comments,
    and runs commands from stdin when it isn't a terminal
    (`pltr shell < commands.txt`).
  - The shared options where they were missing: `--format/-f`,
    `--output/-o` and `--profile/-p` (some commands keep a short flag for
    something else, as their help shows), and the paging options on every
    paged command.
- For developers:
  - `pltr.contract`, the shared output, error, exit-code and confirmation
    layer, with command metadata (beta, destructive, paged, SDK methods) that
    `pltr.contract.iter_commands` lists for the whole tree (#187). See
    `docs/development/command-contract.md`.
  - A CI check of every SDK call in `src/pltr` against the real SDK
    signatures and preview rules (#185): `tests/test_sdk_call_guardrail.py`,
    `scripts/check_sdk_calls.py` and `docs/development/sdk-guardrail.md`.
  - `stub_foundry_http` (`tests/conftest.py`): tests run against a real
    `FoundryClient` with only HTTP faked (#179). A CLI-wide contract test runs
    every command against stubbed 404 and 400 responses.
  - `scripts/generate_api_commands.py` regenerates `pltr api` (a test fails
    when it is stale); `scripts/coverage.py` reports which commands reach each
    SDK method. CI runs both and the SDK call check.
  - `pltr.manifest` (`build_manifest`, `search`, `find_command`, ...) and
    `scripts/check_command_metadata.py`, which checks each curated command's
    `sdk=` metadata against the SDK methods its service calls reach.
  - `scripts/generate_skill_reference.py` generates the agent skill's command
    reference from the manifest. A test fails when the committed reference is
    stale, or when a hand-written skill file mentions a command or option that
    doesn't exist; `--check` runs the same checks.
  - `tests/test_docs_examples.py` checks every `pltr` example in the README,
    `docs/` and `claude_skill/` against the real command tree.
  - `scripts/smoke.py`, a live smoke test for maintainers (#189). Run against
    a real stack, it drives the real `pltr` with `--format json`, checks the
    result and the output contract (exit code, one JSON document on stdout,
    JSON Lines and the structured error on stderr), and prints a
    pass/fail/skip table (`--markdown` to paste into a pull request).
    Read-only checks cover every area and one `pltr api` command per
    namespace; `--allow-writes --scratch-folder RID` adds a write pass that
    moves everything it creates to the trash; `--include-admin` adds admin
    checks and never deletes permanently. Inputs come from `smoke.toml`
    (example: `scripts/smoke.example.toml`), flags or earlier checks; a check
    without its input is skipped. `docs/development/live-verification.md`
    explains how to run it and lists every assumption of this release that
    wasn't verified live, with the check that covers it.

### Changed

#### Everywhere

- Python warnings raised while a command runs (for example the SDK's
  `UserWarning`s) print as `Warning: ...` on stderr, or as JSON warning lines.
- Usage errors found while parsing arguments (a missing argument, an unknown
  option) are JSON errors when the command was asked for JSON (`--format json`
  or `PLTR_FORMAT=json`).
- An unexpected error prints one `Error: ...` line instead of a traceback; set
  `PLTR_DEBUG=1` for the traceback. An unexpected failure inside the SDK says
  "foundry-platform-sdk failed unexpectedly" and asks you to report it.
- pltr starts about three times faster: `pltr --help` took a median of
  1017 ms and now 370 ms (15 runs each, same machine), and shell completion
  speeds up the same way. Commands import the SDK's model packages when they
  run, not at startup.
- `pltr <group> --help` shows the group's own help, with RID formats and
  examples, for `dataset`, `folder`, `project`, `resource`, `resource-role`,
  `space`, `ontology`, `orchestration`, `media-sets`, `connectivity` and
  `verify`; a one-line description used to replace it. `pltr --help` keeps
  the one-line summaries. `admin`, `sql` and `shell` show their modules'
  descriptions, and `pltr cp --help` its full description.
- pltr depends on prompt-toolkit instead of click-repl, and declares click,
  which it imports (click-repl used to bring it in). It also declares httpx,
  pydantic, pydantic-core and typing-extensions, which it imports too.
- typer and click are capped at the versions pltr is tested with
  (`typer>=0.16.0,<0.17`, `click>=8.2.0,<8.2.2`). typer 0.26 and later no
  longer install click and don't handle pltr's exit codes, typer 0.21 to 0.25
  hide the `[beta]` label, and click 8.2.2 lets destructive commands run
  without `--yes` when stdin isn't a terminal. If another tool needs newer
  versions, install pltr in its own environment (`pipx install pltr-cli` or
  `uv tool install pltr-cli`). CI installs the built wheel without the lock
  file on Linux and Windows and runs it.
- **The Claude Code skill in `claude_skill/` was rewritten** (#188).
  `SKILL.md` is a short guide: headless authentication, the JSON, stdout and
  stderr rules and exit codes, safety rules for destructive commands, beta
  labels, RIDs, finding commands with `pltr commands`, curated commands versus
  `pltr api`, and common workflows. The command reference is generated from
  the manifest: `reference/index.md`, `reference/curated/<group>.md` and
  `reference/api/<namespace>.md`. If you copied the skill to
  `~/.claude/skills/`, copy the directory again.
- For library users: `DatasetService.preview_rows()` is now
  `preview_table()` and returns the `pyarrow.Table`; `decode_arrow_rows()` is
  now `arrow_table()`; `pltr.services.resource.RESOURCE_TYPES` is now the
  function `resource_types()`.

#### Authentication, `verify` and `configure`

- **Breaking:** `pltr verify` uses the SDK, not the internal
  `/multipass/api/me` endpoint. Its table shows the auth source, auth type,
  host and the user's fields (the groups row is gone), and it fails with exit
  code 3 (no usable or rejected credentials), 4, 5 or 7.
- **Breaking:** `configure configure` never prompts when stdin is not a
  terminal: missing values are a usage error (exit 2) that names the options
  to pass. Replacing an existing profile asks first (`--yes` skips).
  `--auth-type` accepts only `token` or `oauth`, and credentials of the other
  auth type (such as `--client-id` with `--auth-type token`) are rejected
  instead of dropped.
- **Breaking:** `configure delete` asks unless `--yes`/`-y`; `-f` is
  `--format`. `configure delete` and `configure set-default` exit with 5 for
  an unknown profile. Deleting a profile whose keyring entry is already gone
  removes it, with a warning.
- **Breaking:** `configure` exits with code 3, pointing to environment
  variable authentication, when the system keyring can't be used; it crashed
  with a traceback.
- **Breaking:** the commands that call Foundry endpoints directly
  (`dataset schema apply`, the `ontology object-type-create` and
  `link-type-create` fallback, `language-models list`, `status` and `enroll`)
  always use `https://` with the profile's or environment's host, like the
  SDK client.
- Keyring calls have a time limit (`PLTR_KEYRING_TIMEOUT`), and any keyring
  failure gives an error that points to the environment variables.
- Reading settings or profiles no longer creates `~/.config/pltr`; it is
  created when something is saved.

#### `alias`, `completion` and `shell`

- **Breaking:** `alias remove`, `alias clear`, and `alias import` when it
  replaces aliases, ask unless `--yes`/`-y`. Answering "no" exits with 1.
- **Breaking:** an unknown alias exits with 5 in `alias show`, `edit`,
  `remove` and `resolve`; `show` and `resolve` printed a message and exited
  with 0. Name clashes without `--force`, reserved names, circular references
  and bad import files are usage errors (exit 2; was 1). An alias can't use
  the name of any top-level command (`folder`, `space`, `api` and others were
  allowed and shadowed the command).
- **Breaking:** `completion show` prints the bare script (it printed a panel
  with line numbers), so `eval "$(pltr completion show --shell bash)"` works.
  An unsupported or undetectable shell exits with 2.
- `pltr shell` prints its banner and "Goodbye!" on stderr, and only when
  stdin is a terminal. It runs each line as its own `pltr` invocation.

#### `folder` and `space`

- **Breaking:** `space delete` doesn't prompt when stdin is not a terminal.
- `space update` reads the space and sends back the fields you don't change.
  `Space.replace` resets omitted fields, so the description was cleared and
  the default role set and usage account were reset.
- `folder create --parent-folder` help says that folders can only be created
  inside a project.

#### `project`, `resource`, `resource-role` and `cp`

- **Breaking:** `project remove-orgs` and `resource remove-markings` ask for
  confirmation. `project delete`, `resource delete`,
  `resource permanently-delete` and `resource-role revoke` don't prompt when
  stdin is not a terminal.
- **Breaking:** `resource list` and `resource search` no longer accept `-o`
  for `--format`. `-f` stays `--folder-rid` there, so `--format` and
  `--output` have no short flags on these two commands.
- **Breaking:** `resource list` and `resource search --type` take the API's
  resource type names (`FOUNDRY_DATASET`, `COMPASS_FOLDER`, ...;
  case-insensitive, with `dataset` and `folder` as short names). An unknown
  type is a usage error. `--type dataset` used to match nothing.
- **Breaking:** `resource-role grant` and `revoke` take
  `--principal-id USER_OR_GROUP_ID` (a UUID) or `--everyone`, and
  `--role ROLE_ID`. Usernames and group names are rejected (exit 2).
- **Breaking:** `project delete` moves the project to the trash
  (`Resource.delete`) after checking that the RID is a project. Restore it
  with `pltr resource restore`.
- **Breaking:** `project list` without `--space-rid` reads every page of every
  space, and rejects `--page-token` and `--max-pages`.
- **Breaking:** `resource search` stops after `--max-folders` folders (default
  1000) with a warning that the results may be incomplete; it used to fail
  and lose what it had found. An empty query is a usage error.
- **Breaking:** `cp` prints the resources it created (JSON:
  `{"data": [...]}`) and its progress on stderr. When some items of a folder
  fail, it copies the others (unless `--fail-fast`) and exits with the first
  failure's error; it exited with 0.
- JSON shapes worth knowing: `project list-orgs` prints organization RIDs,
  `resource list-markings` marking IDs, and `resource-role list`
  `{"data": [{"resourceRolePrincipal": {...}, "roleId": "..."}]}`. The API
  returns IDs only, so the names and descriptions pltr used to show were
  always empty.
- `project update` reads the project and sends back the field you don't
  change; `Project.replace` cleared an omitted description.
- `project create` looks up the calling user (`admin.User.get_current`) as
  the default owner; `--owner-type` accepts `USER` or `GROUP` and needs
  `--owner-id`. `project create-from-template --var` is optional.
- `project list` without `--space-rid` lists the projects of every space.
- `resource-role list --principal-type` filters each page locally; the API
  has no such filter.
- `cp --dry-run` prints the resources it would copy. Skipped items are
  warnings.
- **Breaking:** a `cp` dataset copy fails when its schema can't be copied (see
  Breaking changes). The schema is read from `--branch` (it was read from the
  default branch) and put on the committed copy of the files, on the same
  branch. The API doesn't report the source's dataframe reader, so the copy
  gets `CSV` when every copied file is a `.csv` file, `AVRO` when every file
  is `.avro`, and the API's default (`PARQUET`) otherwise. A dataset with no
  files on `--branch` is copied empty, without a schema, with a message.
- `cp --help` explains the RID arguments and how datasets, schemas and
  failures are handled.

#### `dataset`

- **Breaking:** `--branch` defaults to the dataset's default branch (the
  API's choice, usually `master`) instead of the literal `master`, on
  `files list`, `upload`, `get`, `delete` and `info`, `transactions start`,
  `schema set`, `views get` and `jobs list`. `schema apply` still defaults to
  `master`.
- **Breaking:** `schema set`, `schema apply`, `views remove-datasets` and
  `views replace-datasets` ask for confirmation. `branches delete`,
  `files delete` and `transactions abort` don't prompt when stdin is not a
  terminal.
- **Breaking:** `transactions list` lists every branch's transactions unless
  you pass `--branch`.
- **Breaking:** an invalid RID is a usage error (exit 2).
- **Breaking:** `files get` prints the downloaded file's metadata on stdout.
- JSON shapes worth knowing: transactions are `Transaction` objects, so read
  `.rid`; `preview` prints `{"data": [{column: value}]}` (BINARY values in
  base64); `schedules list` prints schedule RIDs only, as the API returns
  them; `transactions build` prints the build RID as a JSON string;
  `schema get` and `schema set` print the API's response, with the schema
  under `schema.fieldSchemaList`; `files upload` of a directory and
  `files get --recursive` print `{"data": [...]}` of files.
- `schema get` no longer warns that it needs API preview access: the endpoint
  is GA.
- `branches create --parent BRANCH` (default `master`) starts the new branch
  at the parent's latest transaction. `branches delete master` is refused
  (exit 2).
- A leading `/` in a dataset file path is dropped (the API rejects it).
- `preview` gives duplicate column names a `_2`, `_3` suffix with a warning,
  like `sql`, instead of letting the later column overwrite the earlier one.

#### `ontology`

- **Breaking:** `object-search --query/-q` is gone: the API has no free-text
  search. Use `--where` with the API's typed query, for example
  `{"type": "eq", "field": "department", "value": "Engineering"}`. `--query`
  is hidden for one release and fails with a usage error that suggests the
  `--where` equivalent.
- **Breaking:** `object-aggregate` takes the API's aggregation objects in
  `--aggregation`, for example
  `[{"type": "count"}, {"type": "avg", "field": "salary"}]`. The
  `AGGREGATIONS` argument still works for one release, with a warning. The
  documented `{"count": "count"}` shape never worked and is rejected.
- **Breaking:** `object-linked` fetches one page by default, and
  `object-list` uses the API's default page size.
- **Breaking:** `action-apply` exits with 6 when Foundry reports the
  parameters invalid (nothing was applied). `action-validate` exits with 0 and
  prints the validation result, valid or not.
- JSON shapes worth knowing: `ontology list` prints `{"data": [...]}`;
  `object-search` prints `{"data", "nextPageToken", "totalCount"}`;
  `object-count` prints `{"count": N}`; `object-aggregate` prints the API's
  `{"accuracy", "data": [{"group", "metrics"}]}`; `action-apply` and
  `action-validate` print `{"operationId", "validation", "edits"}`;
  `query-execute` prints `{"value": ...}`; `object-type-create` and
  `link-type-create` print Foundry's response body, or `null`.

#### `admin`

- **Breaking:** user and group IDs must be UUIDs: `user get`, `markings`,
  `revoke-tokens`, `delete` and `batch-get`, and `group get`, `delete` and
  `batch-get` reject anything else (exit 2) with a hint to find the ID with
  `admin user search` or `admin group search`. Usernames, emails and group
  names never worked.
- **Breaking:** `user delete`, `user revoke-tokens`, `group delete`,
  `org replace` and `marking replace` don't prompt when stdin is not a
  terminal. Answering "no" exits with 1; it printed "Operation cancelled." and
  exited with 0.
- **Breaking:** `marking create --category-id` and `org create --admin-id`
  (at least one) are required, as the API requires them.
- JSON shapes worth knowing: the `batch-get` commands print
  `{"data": {"<ID>": {...}}}`; `user markings` prints
  `{"view": ["<marking ID>", ...]}`.
- `org replace` and `marking replace` keep the current description (and, for
  organizations, the host) unless you pass `--description` or `--host`; they
  were cleared. This reads the organization or marking first, which needs
  view permission.
- `user list` uses the API's default page size unless you pass `--page-size`.
- The help of `admin user`, `group`, `org`, `marking` and `role` says how each
  is identified and where to find the IDs.

#### `sql`, `streams` and `media-sets`

- **Breaking:** `sql execute`, `results`, `wait` and `export` (to a `.json`
  file) print `{"data": [...]}`, one object per row keyed by column name.
  Binary values are base64, NaN and infinity are `null`, and duplicate column
  names get a `_2`, `_3` suffix, with a warning. `execute` used to print
  `Query ID:` and `Status:` lines before the JSON on stdout.
- **Breaking:** `sql submit`, `status` and `cancel` print the API's query
  status (`{"type": "running", "queryId": "..."}`, `succeeded`, `failed` with
  `errorMessage`, or `canceled`) and take `--format`. Capture an ID with
  `pltr sql submit "..." --format json | jq -r .queryId`.
- **Breaking:** a query that fails or is canceled exits with 7 from `execute`,
  `submit`, `wait` and `export`. Reaching `--timeout` exits with 7
  (`timeout`) and leaves the query running. `sql results` exits with 6 while
  the query is running and 7 if it failed; it no longer checks the status
  first (the API waits up to a minute). `sql wait` always prints the rows.
- **Breaking:** `sql cancel` asks for confirmation. `streams stream reset` and
  `media-sets abort` don't prompt when stdin is not a terminal, and "no"
  exits with 1. `media-sets commit` no longer asks: committing deletes
  nothing.
- **Breaking:** stream schemas use the API's format,
  `{"fields": [{"name": "id", "schema": {"nullable": false, "dataType": {"type": "long"}}}], "keyFieldNames": ["id"]}`.
  The documented `{"fieldSchemaList": [...]}` shape never worked and is
  rejected (exit 2). `--type` accepts only `LOW_LATENCY` and
  `HIGH_THROUGHPUT`.
- **Breaking:** `media-sets download` and `thumbnail-retrieve` exit with 2
  when the output file exists and `--overwrite` isn't given, and stream the
  content to a temporary file that replaces the output file only when the
  download is complete: a failed download leaves no partial file and keeps
  the file it would have replaced. An empty thumbnail exits with 7.
- JSON shapes worth knowing: `media-sets get` prints the API's media item
  info; `get-by-path` prints `{"mediaItemRid": "..."}`; `create` prints the
  transaction ID as a string; `upload` prints
  `{"mediaItemRid", "mediaSetViewRid"}`; `streams stream create`, `get` and
  `reset` print the stream; `streams dataset create` no longer prints a
  stream RID (the API returns none).
- Media set RIDs look like `ri.mio.main.media-set.<uuid>`; the help used to
  say `ri.mediasets.main.media-set...`.

#### `orchestration`, `data-health`, `functions` and `models`

- **Breaking:** `orchestration builds search` requires a filter (`--where`
  or one of the filter options), as the API does.
- **Breaking:** `orchestration builds cancel` and `schedules replace` ask for
  confirmation; `schedules delete` no longer prompts when stdin is not a
  terminal. `data-health check replace` asks; `check delete` no longer
  prompts when stdin is not a terminal.
- **Breaking:** `data-health check delete` skips the question with
  `--yes/-y`; `--force` is a hidden alias and `-f` is `--format`.
- **Breaking:** `data-health report get CHECK_RID CHECK_REPORT_RID`: the API
  addresses a report through its check. Find report RIDs with
  `data-health report latest`.
- **Breaking:** `orchestration schedules run` prints the schedule run (its
  result and the build it started) instead of a success message.
- **Breaking:** `models version get MODEL_RID MODEL_VERSION_RID` takes a
  version RID, not a name such as `v1.0.0`; list them with
  `models version list`.
- JSON shapes worth knowing: `builds get-batch` and `jobs get-batch` print
  `{"data": {"<RID>": {...}}}`; `functions query execute` prints
  `{"value": ...}`; `models model create` and `get` print `{"rid": ...}`
  (a model has no other fields in the API).
- `functions query execute-by-rid` looks the query up by RID, then executes
  that version by API name: the API has no execute-by-RID endpoint.
- `data-health report get` shows the status and message as table columns
  instead of a colored line.

#### `connectivity`, `language-models` and `audit`

- **Breaking:** the `connectivity import` commands take the connection RID
  first, as the API nests imports under connections:
  - `import file CONNECTION_RID DATASET_RID --name NAME --mode SNAPSHOT|APPEND|UPDATE [--subfolder PATH] [--branch NAME] [--filters JSON]`
    (was `import file CONNECTION_RID SOURCE_PATH TARGET_DATASET_RID [--config JSON] [--execute]`);
  - `import table CONNECTION_RID DATASET_RID --name NAME --mode SNAPSHOT|APPEND --config JSON [--allow-schema-changes] [--branch NAME]`
    (was `import table CONNECTION_RID SOURCE_TABLE TARGET_DATASET_RID [--config JSON] [--execute]`);
  - `get-file` and `get-table CONNECTION_RID IMPORT_RID` (was `IMPORT_RID`),
    and `list-file` and `list-table CONNECTION_RID` (was an optional
    `--connection/-c`).

  None of these could succeed before, so the old forms aren't kept.
- **Breaking:** `connection update-secrets` and `update-export-settings` ask
  for confirmation, because they overwrite the current values.
- **Breaking:** `connection get-config`, `language-models anthropic messages`,
  `messages-advanced` and `openai embeddings` default to a table; they
  defaulted to JSON.
- **Breaking:** `audit list` fetches one page by default and stops paging at
  the first empty page: without `--end-date` the API always returns a next
  page token.
- **Breaking:** `audit get` never writes to a terminal: pass `--output FILE`
  (`-` for stdout) or redirect stdout.
- JSON shapes worth knowing: `connection get`, `create` and
  `upload-jdbc-drivers` print the API's `Connection`; `get-config` prints the
  configuration itself; the import commands print the API's `FileImport` or
  `TableImport`; `anthropic messages` prints the API's response (`content`,
  `stopReason`, `usage`); `openai embeddings` prints `data` as a list of
  vectors; `language-models list` prints `{"data": [...]}` with each model as
  the endpoint returned it, without the values pltr used to fill in.
- `anthropic messages-advanced` reports unknown request fields (such as
  `max_tokens` instead of `maxTokens`) and invalid requests as usage errors
  before sending anything. The thinking example in its help used `budget`;
  the field is `budgetTokens`.
- The model argument of `anthropic messages`, `messages-advanced` and
  `openai embeddings` is the model's API name, not a RID.
- `language-models list`, `status` and `enroll` try `/api/v2/languageModels`
  first (they called `/v2/...` at the host root), skip answers that aren't
  JSON, and when every endpoint fails, report each endpoint's status.
- `openai embeddings --encoding` accepts only `float` or `base64`, and
  `audit list` dates must be `YYYY-MM-DD`.
- `audit get` streams the log file; a failed download leaves no partial
  `--output` file and keeps an existing one.

#### `widgets`, `aip-agents` and `third-party-apps`

- **Breaking:** `widgets release delete` doesn't prompt when stdin is not a
  terminal, and "no" exits with 1.
- Every command in these groups calls a beta endpoint, with `preview=true`.
  `third-party-apps get` shows only the RID: the API returns nothing else.

### Deprecated

These still work in this release, print a deprecation warning and are hidden
from `--help`. They will be removed in the next release.

- `--confirm`, an alias of `--yes`, on `space delete`, `project delete`,
  `resource-role revoke`, `streams stream reset`, `admin user delete`,
  `admin user revoke-tokens`, `admin group delete`, `admin org replace` and
  `admin marking replace`.
- `--force`, an alias of `--yes`, on `configure delete`, `resource delete`,
  `resource permanently-delete` and `data-health check delete`.
- `--no-confirm`, an alias of `--yes`, on `alias remove` and `alias clear`;
  their `--confirm` (the old default) does nothing.
- `--preview`, which does nothing now: on every `sql` command (also
  `--no-preview`), every `streams`, `functions` and `models` command, every
  `media-sets` command except the new `clear` (#179 had removed it from
  `get`, `download` and `upload-temp`, whose endpoints became GA; it is back
  as a no-op), `orchestration schedules get`, `create` and `replace`,
  `data-health check get`, `create`, `replace` and `delete` and
  `report get`, `language-models anthropic messages`, `messages-advanced`
  and `openai embeddings`, and `third-party-apps get`.
- `media-sets commit --yes/-y`: commit no longer asks.
- `ontology object-aggregate`'s `AGGREGATIONS` argument (use
  `--aggregation`) and `--filter` (use `--where`).
- `admin group create --org-rid` (use `--organization`).
- `admin org available-roles --page-size` and `--page-token`: they have no
  effect; the API returns every role in one response.
- `resource search --page-size` (use `--limit`).
- `resource-role grant` and `revoke --principal-type/-t`: ignored; the
  principal's ID is enough.
- `cp --debug`: set `PLTR_DEBUG=1` instead.
- The `page_size` setting (`settings.json` in the configuration directory):
  no command reads it, since list commands use the API's page size unless
  you pass `--page-size`. New settings files don't get it, and an existing
  one is accepted and ignored.

### Removed

- Commands that could never succeed:
  - `connectivity connection list`: the SDK has no endpoint that lists
    connections. Its folder-scan fallback (and
    `PLTR_CONNECTIONS_FALLBACK_START_FOLDER_RID`) is gone too. Data Connection
    sources appear in `pltr folder list FOLDER_RID` as `MAGRITTE_SOURCE`
    resources.
  - `dataset views list`: the SDK has no endpoint that lists a dataset's
    views.
  - `resource get-metadata`: the SDK has no `Resource.get_metadata`. Use
    `pltr resource get`.
  - `resource-role get-principal-roles` and `get-available-roles`: the SDK has
    no such endpoints. `pltr resource-role list` shows the roles granted on a
    resource.
  - `widgets dev-mode get`, `disable` and `pause` (the SDK doesn't have them),
    and `widgets dev-mode enable`, which alone would be confusing. Use
    `pltr api widgets dev-mode-settings enable` (or `set-widget-set-by-id`)
    and the `dev-mode-settings-v2` commands.
- Options:
  - `connectivity import file` and `table --execute` (use
    `import execute-file` and `execute-table`), `import file --config/-c` (use
    `--name`, `--mode`, `--filters`, `--subfolder` and `--branch`), and
    `import list-file` and `list-table --connection/-c` (now the
    `CONNECTION_RID` argument). None of them ever worked.
  - `space list --organization-rid/-org`: `Space.list` has no organization
    filter, and the option never worked. It is hidden for one release and
    exits with 2, explaining how to filter the JSON output on
    `organizations`.
  - `ontology object-search --query/-q` (see Changed) and
    `dataset views create --description` (views have no description): hidden
    for one release, and they fail with an explanation.
  - `-o` as the short form of `--format` on `resource list` and
    `resource search`, and `-f` as the short form of `--force` on
    `configure delete`, `resource delete`, `resource permanently-delete` and
    `data-health check delete` (`-f` is `--format` now).
  - The token-usage line on stderr of `language-models anthropic messages`,
    `messages-advanced` and `openai embeddings`; it always printed 0. The
    output has the token counts.
- The hand-written skill reference (`claude_skill/reference/quick-start.md`
  and `claude_skill/reference/*-commands.md`) and workflows
  (`data-analysis.md`, `data-pipeline.md`, `permission-management.md`). They
  documented commands and flags that don't exist. The new workflows are
  `explore-data.md`, `builds-and-schedules.md` and `permissions.md`.
- For library users: `DatasetService.list_files_paginated`, `get_branches`,
  `get_transactions`, `get_views`, `get_schedules`, `get_jobs`,
  `get_branch_transactions`, `get_transaction_status` and `preview_data`;
  `AdminService.list_users_paginated` and `_serialize_response`;
  `ObjectTypeService.list_outgoing_link_types`;
  `OntologyObjectService.list_objects_paginated`;
  `ResourceRoleService.bulk_grant_roles` and `bulk_revoke_roles`;
  `AliasManager.display_aliases`. Services return SDK models instead of
  snake_case dicts, and let SDK exceptions propagate.
- For library users: `DatasetService.create_dataset`, `get_schema`,
  `list_files`, `create_transaction` and `delete_dataset` (use `create`,
  `get_dataset_schema`, `list_dataset_files`, `start_transaction` and
  `ResourceService.delete_resource`); the legacy output helpers no command
  uses any more: `pltr.utils.formatting` (`OutputFormatter`),
  `pltr.utils.progress`, `pltr.utils.pagination`,
  `BaseService._paginate_iterator`, `_paginate_response` and
  `_serialize_response`, and the unused completion helpers
  `complete_ontology_action`, `complete_file_path`,
  `setup_completion_environment`, `handle_completion` and
  `COMPLETION_FUNCTIONS`. Use `pltr.contract` (`emit`, `spinner`,
  `collect_pages`, `to_jsonable`).

### Fixed

- Commands that could never succeed (#182):
  - dataset: `branches list` and `create`, `branches transactions`,
    `transactions list` and `build`, `jobs list`, every `views` command and
    `preview`;
  - ontology: `action-apply`, `action-validate`, `object-aggregate`,
    `object-search`, `object-count`, and `object-linked` (#179);
  - filesystem: `folder batch-get`, `space create`, `project delete`,
    `resource batch-get`, `resource batch-get-by-path`, and
    `resource-role grant`, `revoke` and `list`;
  - admin: `user search`, `group search`, `group create`, `marking create`,
    `org create`, `org available-roles`, `role get` and every `batch-get`;
  - orchestration: `builds search`, `builds get-batch`, `jobs get` and
    `jobs get-batch`;
  - `data-health report get`, `functions query get-by-rid` and
    `execute-by-rid`, `models version get` and `list`,
    `media-sets get-by-path`, and the `connectivity import` commands.
- Commands that failed unless you passed `--preview` (#184):
  `orchestration schedules get`, `create` and `replace`, the `data-health`,
  `functions`, `models` and `streams` beta commands, `media-sets` beta
  commands, `language-models anthropic messages`, `messages-advanced` and
  `openai embeddings`, and `third-party-apps get`. Commands that called GA
  endpoints with `preview` no longer print the SDK's warning.
- Output that read fields the API doesn't return and printed empty values,
  `N/A`, `unknown` or `None` (#183): `folder`, `space`, `project`,
  `resource`, `resource-role`, `connectivity connection` and `media-sets`
  tables; `ontology action-apply`, `action-validate`, `object-count` and
  `query-execute`; `models model create`. `ontology object-get`,
  `object-list` and `object-linked` printed `{}` for every object (#179).
- `sql` JSON output wasn't valid JSON (status text on stdout).
- `project list` filtered on a type and RID prefix that projects don't have,
  so it most likely never listed anything.
- `media-sets download` failed with a `TypeError`, and `upload` and
  `upload-temp` sent the file object instead of its bytes (#179).
- `dataset files upload --transaction-rid` also sent `branchName=master`,
  which the API rejects.
- `dataset schema set` checks the schema against the API's field types and
  reports problems as usage errors.
- `audit list` could page forever; `audit get` printed `[...]` in log content
  as terminal markup.
- `pltr cp` never copied a dataset's schema: it passed the whole schema
  response where the API takes the schema itself, and put it on the new
  dataset before any transaction existed, so the schema was always skipped
  with a warning. It now copies the files, commits them, and then puts the
  source's schema on the committed transaction of the same branch.
- `pltr cp` moves a partly copied dataset to the trash when a step fails,
  including listing the source's files (the cleanup called a method that
  doesn't exist), and `--fail-fast` no longer counts a failure once per
  folder level.
- The `data-health check create` help example used the severity `WARNING`;
  severities are `MODERATE` and `CRITICAL`.
- `FOUNDRY_HOST` with `FOUNDRY_TOKEN` (or client credentials) failed with "No
  profile specified and no default profile configured" unless a profile
  existed.
- The direct-HTTP commands sent `Authorization: Bearer None` with OAuth
  profiles and ignored environment-variable auth. They now share the SDK
  client's credentials (one OAuth token for both).
- A system keyring that blocks (the macOS Keychain over SSH, an agent
  sandbox) no longer hangs pltr, a missing keyring backend gives a clear error
  instead of a traceback (#144), and corrupted stored credentials say which
  profile to configure again.
- Aliases work with the `pltr` executable; they only worked with
  `python -m pltr`.
- `pltr shell` works on click 8.2: it printed an empty error box at start and
  crashed on the first command.
- `pltr completion` scripts complete commands, options, option values and the
  `pltr api` tree in bash, zsh and fish; the scripts it installed never
  completed anything.
- Tracebacks (now printed only with `PLTR_DEBUG=1`) showed every frame's
  local variables, which included the bearer token, the `Authorization`
  header and the OAuth client secret. They show the code and the error only.
- A command whose API call succeeded, a write included, failed with exit
  code 1 and printed no result when the RID completion cache
  (`~/.cache/pltr`) couldn't be written, for example with a read-only or
  missing home directory in a container or agent sandbox; a retry repeated
  the write. The cache is best-effort now, and a corrupted cache file is
  replaced.

## [0.16.0] - 2026-06-25

### Changed

- Requires foundry-platform-sdk 1.95.0 or later (was 1.69.0) (#173).

### Removed

- **Breaking:** Python 3.9 support. pltr needs Python 3.10 or later, like the
  SDK since 1.71 (#173).

## [0.15.0] - 2026-04-17

### Added

- `pltr language-models list`, `status` and `enroll` (#164, #165; #167,
  #168). They call Foundry endpoints directly: the SDK has no methods for
  them.
- `pltr ontology object-type-create` and `link-type-create` (#143; #169).
  They also call Foundry endpoints directly.

### Fixed

- `pltr sql execute` decodes the Arrow IPC results the API returns into rows
  (#171). pltr now depends on pyarrow.
- `language-models anthropic messages` and `messages-advanced` send message
  roles in upper case (`USER`, `ASSISTANT`), as the API requires (#163;
  #166).

## [0.14.1] - 2026-02-28

### Fixed

- `language-models anthropic messages` and `messages-advanced` pass their
  parameters to the SDK as keyword arguments; they passed a `request` object
  the SDK doesn't accept (#159; #161).

## [0.14.0] - 2026-02-28

### Fixed

- `project list` uses filesystem endpoints the SDK has (#155).
- `resource list` and `resource search` walk folders instead of calling
  methods the SDK doesn't have (#156).
- `connectivity connection list` works with current SDK clients, falling
  back to scanning folders (#154).
- `orchestration builds search` handles beta (preview) mode and paging
  (#153).
- `folder list` and `resource get-by-path` failures show the error details;
  they printed an empty message (#157, #158).

## [0.13.1] - 2026-02-25

### Added

- `pltr data-health`: `check get`, `create`, `replace` and `delete`, and
  `report get` (#37; #131).
- `pltr audit list` and `audit get` for audit log files (#35; #132).
- `pltr widgets`: `get`, `release list/get/delete`, `repository get` and
  `dev-mode get/enable/disable/pause` (#31; #133).

### Changed

- **Breaking:** `folder create` and `dataset create` require
  `--parent-folder`. The old default, the root folder
  `ri.compass.main.folder.0`, doesn't exist on some stacks, so creates
  failed silently (#137; #140).

### Fixed

- `--format json` and `--format csv` print to stdout; before, they only
  took effect with `--output` (#136; #141).
- Ontology object commands use the parameter names of foundry-platform-sdk
  1.69.0 (`select` and `branch`) (#135; #139).

## [0.13.0] - 2026-02-04

### Added

- `pltr functions`: `query get`, `get-by-rid`, `execute` and
  `execute-by-rid`, and `value-type get` (#109; #116).
- `pltr streams`: `dataset create` and `stream create`, `get`, `publish`,
  `publish-batch` and `reset` (#29, #110; #118).
- `pltr language-models`: `anthropic messages`, `anthropic messages-advanced`
  and `openai embeddings` (#120; #123).
- `pltr models`: `model create`, `model get`, `version get` and
  `version list` (#121; #124).
- `project create --owner-id` and `--owner-type` (#129).

### Changed

- Requires foundry-platform-sdk 1.69.0 (was 1.27.0) (#117).
- **Breaking:** `space create` requires `--enrollment-rid`, `--organization`
  and `--deletion-policy-org`, as SDK 1.69.0 does (#126; #127).

### Removed

- **Breaking:** `space list-members`, `space add-member`,
  `space remove-member`, `space batch-get`, `project batch-get` and
  `resource move`. SDK 1.69.0 removed their endpoints (#126; #127).

### Fixed

- `admin user list` and `admin group list` show paged results (#114).
- Project, space, folder and resource commands updated for the
  SDK 1.69.0 API changes (#126; #127).

## [0.12.0] - 2026-01-27

### Added

- `pltr cp`: copy datasets, or folders with their contents, into another
  folder (#95; #96).
- A Claude Code skill in `claude_skill/` (#97).
- Admin: `user delete`, `user batch-get`, `group batch-get`,
  `role batch-get`, `org create`, `org replace`, `org available-roles`, and
  `marking list/get/batch-get/create/replace` (#65; #98).
- Orchestration: `builds get-batch` and `schedules runs` (#69; #99).
- Media sets: `thumbnail-calculate`, `thumbnail-retrieve` and `upload-temp`
  (#70; #100).
- Filesystem: `resource delete`, `restore`, `permanently-delete`,
  `add-markings`, `remove-markings`, `list-markings`, `access-requirements`
  and `batch-get-by-path`; `project add-orgs`, `remove-orgs`, `list-orgs` and
  `create-from-template` (#72; #101).
- Connectivity: `connection create`, `get-config`, `update-secrets`,
  `update-export-settings` and `upload-jdbc-drivers` (#67; #102).
- `--page-size`, `--page-token`, `--max-pages` and `--all` on
  `admin user list`, `orchestration builds search`, `ontology object-list`
  and `dataset files list` (#46; #106).
- `pltr dataset preview` (#105). pltr now depends on pandas.
- `pltr third-party-apps get` (#30; #107).
- `pltr aip-agents`: `get`, `sessions list/get` and `versions list` (#108;
  #112).

### Changed

- **Breaking:** the commands that gained paging options fetch one page by
  default; pass `--all` for every page (#106).

### Fixed

- SQL commands call the SQL query endpoints in preview mode, which they
  required; `--preview` is on by default (#93).

## [0.11.0] - 2025-10-09

### Added

- `ontology object-count` and `ontology object-search` (#68; #90).

### Fixed

- `dataset files get` downloads with `Dataset.File.content`; it called a
  method the SDK doesn't have (#91).

## [0.10.0] - 2025-09-30

### Added

- `resource get-by-path`: get a resource by its Compass path (#86).

### Fixed

- `--format json` prints plain JSON without terminal markup, so it can be
  piped (#87).
- `orchestration builds create --help` documents the build target JSON
  (#87).
- Tables no longer wrap RID columns (#87).

## [0.9.3] - 2025-09-30

No changes to pltr itself; only the version number changed.

## [0.9.2] - 2025-09-24

### Fixed

- `orchestration builds create` sends `fallback_branches` as a list (#84).

## [0.9.1] - 2025-09-12

### Fixed

- `dataset schema apply` applies the inferred schema; it only inferred it
  (#82).

## [0.9.0] - 2025-09-12

### Added

- `dataset schema apply`: infer a dataset's schema from its files and apply
  it, through the endpoints Foundry's web interface uses (direct HTTP calls),
  for stacks where the SDK's schema endpoints needed preview access (#78).

## [0.8.0] - 2025-09-12

### Changed

- `dataset files upload` errors name the Foundry error and suggest a fix
  (#76).

## [0.7.0] - 2025-09-11

### Added

- `dataset schema get` and `dataset schema set`, including `--from-csv` to
  infer column types from a CSV file (#64).
- `dataset branches delete`, `get` and `transactions`; `dataset files delete`
  and `info`; `dataset transactions build`; `dataset views get`,
  `add-datasets`, `remove-datasets`, `replace-datasets` and
  `add-primary-key`; `dataset schedules list`; `dataset jobs list` (#74).

## [0.6.0] - 2025-09-09

### Fixed

- `dataset files upload` sends the file's content (#62).

## [0.5.2] - 2025-09-09

### Fixed

- Dataset file and transaction commands failed with an `AttributeError`;
  they now call the SDK's `Dataset.File` and `Dataset.Transaction` (#59;
  #60).

## [0.5.1] - 2025-09-09

### Added

- `pltr project`, `pltr resource`, `pltr resource-role` and `pltr space`
  (#43; #52).
- `dataset transactions start`, `commit`, `abort`, `status` and `list`, and
  `dataset files upload --transaction-rid` (#48; #53).
- `pltr connectivity`: connections and file and table imports (#36; #54).
- CSV upload examples in `docs/examples/csv-upload.md` (#55).

### Fixed

- `pltr --version` printed 0.1.0 (#50).

## [0.5.0] - 2025-09-03

### Added

- `pltr orchestration`: builds, jobs and schedules (#28; #40).
- `pltr media-sets`: `get`, `get-by-path`, `create`, `commit`, `abort`,
  `upload`, `download` and `reference` (#27; #41).
- `dataset branches list/create`, `dataset files list/get`,
  `dataset transactions list` and `dataset views list/create` (#32; #42).

## [0.4.0] - 2025-08-31

### Added

- `pltr folder`: `create`, `get`, `list` and `batch-get` (#33).

### Fixed

- CI pipeline fixes (#38).

## [0.3.0] - 2025-08-28

### Added

- Command aliases: `pltr alias` (#15).

### Fixed

- `ontology list` and the object type commands called the SDK incorrectly
  (#21, #22; #23).

### Removed

- `--page-size` on ontology commands; their SDK methods didn't take it
  (#23).

## [0.2.0] - 2025-08-15

### Added

- `pltr ontology` (#6), `pltr sql` (#7) and `pltr admin` (#8).
- `pltr shell`, an interactive mode (#9), and `pltr completion` for bash,
  zsh and fish (#11).
- User documentation in `docs/` (#14).

## [0.1.2] - 2025-08-10

### Fixed

- The release workflow (an updated signing action).

## [0.1.1] - 2025-08-10

### Fixed

- The install command in the README is `pip install pltr-cli`.

## [0.1.0] - 2025-08-10

### Added

- First release, published on PyPI as `pltr-cli`: `pltr configure` (token
  and OAuth2 profiles, with credentials in the system keyring),
  `pltr verify`, `pltr dataset get` and `pltr dataset create`.

[Unreleased]: https://github.com/anjor/pltr-cli/compare/v0.16.0...HEAD
[0.16.0]: https://github.com/anjor/pltr-cli/compare/v0.15.0...v0.16.0
[0.15.0]: https://github.com/anjor/pltr-cli/compare/v0.14.1...v0.15.0
[0.14.1]: https://github.com/anjor/pltr-cli/compare/v0.14.0...v0.14.1
[0.14.0]: https://github.com/anjor/pltr-cli/compare/v0.13.1...v0.14.0
[0.13.1]: https://github.com/anjor/pltr-cli/compare/v0.13.0...v0.13.1
[0.13.0]: https://github.com/anjor/pltr-cli/compare/v0.12.0...v0.13.0
[0.12.0]: https://github.com/anjor/pltr-cli/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/anjor/pltr-cli/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/anjor/pltr-cli/compare/v0.9.3...v0.10.0
[0.9.3]: https://github.com/anjor/pltr-cli/compare/v0.9.2...v0.9.3
[0.9.2]: https://github.com/anjor/pltr-cli/compare/v0.9.1...v0.9.2
[0.9.1]: https://github.com/anjor/pltr-cli/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/anjor/pltr-cli/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/anjor/pltr-cli/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/anjor/pltr-cli/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/anjor/pltr-cli/compare/v0.5.2...v0.6.0
[0.5.2]: https://github.com/anjor/pltr-cli/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/anjor/pltr-cli/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/anjor/pltr-cli/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/anjor/pltr-cli/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/anjor/pltr-cli/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/anjor/pltr-cli/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/anjor/pltr-cli/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/anjor/pltr-cli/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/anjor/pltr-cli/releases/tag/v0.1.0
