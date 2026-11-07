# pltr-cli

A command-line interface for the Palantir Foundry Platform API, for people,
scripts and AI agents. Curated commands cover datasets, ontologies, SQL,
builds and schedules, the filesystem, admin and more; `pltr api` adds a
command for every method of the Foundry Platform SDK.

## Overview

pltr is built on the official
[foundry-platform-sdk](https://github.com/palantir/foundry-platform-python).
Every command follows the same rules: `--format json` prints the API's own
JSON, stdout carries only data, errors are structured with documented exit
codes, and destructive commands ask before they change anything.

Foundry's API addresses almost everything by RID (Resource Identifier), for
example `ri.foundry.main.dataset.<uuid>`. Most commands take RIDs, not
names; find them in Foundry's web interface, or with commands such as
`pltr folder list`, `pltr resource get-by-path` and `pltr ontology list`.

## ✨ Key Features

- **Authentication**: token and OAuth2 profiles with credentials in the
  system keyring, or environment variables for CI and agents (no keyring or
  setup needed).
- **Datasets**: branches, files (upload and download, including whole
  directories), transactions, schemas, views and previews.
- **Filesystem**: folders, projects, spaces and resources, including the
  trash, markings and role grants; `pltr cp` copies datasets (their files and
  schema) and folders.
- **Ontology**: object types, objects (list, search, aggregate, count, linked
  objects), actions and queries.
- **Orchestration**: builds, jobs and schedules.
- **SQL**: run queries, wait for them and export their results.
- **More areas**: media sets, streams, functions, models, language models
  (Anthropic Claude, OpenAI embeddings), data health, AIP agents, widgets,
  connectivity (connections and imports), audit logs, and admin (users,
  groups, roles, organizations and markings).
- **Every SDK endpoint**: `pltr api` has a generated command for each method
  of the SDK's V2 client.
- **Built for agents**: JSON output in the API's shape, structured errors,
  exit codes, `--yes` for destructive commands, and `pltr commands`, a
  searchable manifest of every command.
- **Interactive shell** with completion and history, shell completion for
  bash, zsh and fish, command aliases, and multiple profiles.

## Installation

### Recommended: an isolated install

```bash
uv tool install pltr-cli    # or: pipx install pltr-cli
```

This gives pltr its own environment, with the `foundry-platform-sdk` version
pltr was tested with. pltr accepts a range of SDK versions, but its
[`pltr api`](#every-endpoint-pltr-api) commands are generated from one
version: in a shared environment where another package upgrades the SDK, a
command whose SDK method changed fails with a clear error. Upgrade with
`uv tool upgrade pltr-cli` (or `pipx upgrade pltr-cli`).

### Using pip

```bash
pip install pltr-cli
```

### From source

```bash
# Clone the repository
git clone https://github.com/anjor/pltr-cli.git
cd pltr-cli

# Install with uv
uv sync

# Run the CLI
uv run pltr --help
```

## 🚀 Quick Start

### 1. Configure Authentication

Set up your Foundry credentials:

```bash
pltr configure configure
```

Follow the interactive prompts to enter:
- Foundry hostname (e.g., `foundry.company.com`)
- Authentication method (token or OAuth2)
- Your credentials

Running in CI, a container or an AI agent? Skip `configure` and export
`FOUNDRY_HOST` and `FOUNDRY_TOKEN` instead (see [Authentication](#-authentication)).

### 2. Verify Connection

Test your setup:

```bash
pltr verify
```

`verify` fetches your user from Foundry and shows which credentials it used
(`pltr verify --format json` for scripts).

### 3. Start Exploring

```bash
# Who am I?
pltr admin user current

# The ontologies you can see
pltr ontology list

# Failed builds on master
pltr orchestration builds search --status FAILED --branch master

# Spaces, the projects in a space, and a project's or folder's contents
pltr space list
pltr project list --space-rid <space-rid>
pltr folder list <project-or-folder-rid>

# Look up a resource by its path
pltr resource get-by-path "/My Space/My Project/sales"

# Create a folder inside a project or another folder
pltr folder create "Analysis" --parent-folder <project-or-folder-rid>

# Run a SQL query
pltr sql execute "SELECT 1 AS test"

# Datasets are addressed by RID
pltr dataset get <dataset-rid>
pltr dataset branches list <dataset-rid>
pltr dataset files list <dataset-rid>

# Upload files in one transaction, then commit it
TXN=$(pltr dataset transactions start <dataset-rid> --format json | jq -r .rid)
pltr dataset files upload data.csv <dataset-rid> --transaction-rid "$TXN"
pltr dataset transactions commit <dataset-rid> "$TXN"

# Grant a role on a resource (user and group IDs are UUIDs; role IDs come
# from the space's role set)
pltr resource-role list <resource-rid>
pltr resource-role grant <resource-rid> --principal-id <user-or-group-id> --role <role-id>

# Interactive mode
pltr shell
```

### 4. Enable Shell Completion

For the best experience:

```bash
pltr completion install
```

📖 **Need more help?** See the **[Quick Start Guide](docs/user-guide/quick-start.md)** for detailed setup instructions.

## Output, errors and exit codes

pltr is built to be scripted, by people and by agents.

- **stdout is data only.** It carries the result and nothing else, in every
  format. Spinners, progress, success and info messages, warnings,
  confirmation prompts and errors go to stderr.
- **Choose the format** with `--format table|json|csv` (`-f`). The default is
  `table`, whether or not stdout is a terminal. Set `PLTR_FORMAT=json` to
  change the default, for example for agents and CI.
- **`--format json` prints exactly one JSON document**: the Foundry SDK's own
  serialization of the result.
  - Field names are the Foundry API's (camelCase, as in Foundry's REST
    docs), null fields are left out, and times are ISO-8601 strings.
  - Lists use the API's paged shape,
    `{"data": [...], "nextPageToken": "..."}`. `nextPageToken` is left out on
    the last page; pass it to `--page-token` to continue. List commands fetch
    one page by default; use `--all` for every page.
  - A command that returns nothing (for example a delete) prints `null`.
- **In JSON mode stderr carries only JSON Lines.** Informational messages are
  suppressed, and warnings look like
  `{"type": "warning", "message": "..."}`. When a command fails, the last
  stderr line is one structured error:

  ```json
  {"type": "not_found", "message": "FolderNotFound: The given Folder could not be found. (folderRid=ri.compass.main.folder.x)", "exitCode": 5, "statusCode": 404, "errorCode": "NOT_FOUND", "errorName": "FolderNotFound", "errorInstanceId": "…", "parameters": {"folderRid": "ri.compass.main.folder.x"}}
  ```

  Keys that don't apply are left out. In table and CSV mode the same error is
  printed as readable text, including the Foundry `errorName`.

| Exit code | Meaning | Error `type` |
|---|---|---|
| 0 | Success | |
| 1 | Unexpected error, or "no" at a confirmation prompt | `unexpected_error`, `aborted` |
| 2 | Usage error: bad or missing arguments, invalid JSON input, or `--yes` required | `usage_error`, `confirmation_required` |
| 3 | Authentication: no usable credentials, or HTTP 401 | `auth_error` |
| 4 | Permission denied (HTTP 403) | `permission_denied` |
| 5 | Not found (HTTP 404) | `not_found`, `api_not_found` |
| 6 | API validation error (HTTP 400, 422) | `validation_error` |
| 7 | Other API or network error: HTTP 409, 413, 429, 5xx, timeouts, connection errors; or the API's response doesn't match the SDK's model or isn't JSON (`invalid_response`: upgrade pltr, a retry won't help) | `conflict`, `request_too_large`, `rate_limited`, `server_error`, `api_error`, `invalid_response`, `network_error`, `timeout` |

**Destructive commands ask first.** Commands that delete, remove, revoke,
reset, cancel, abort or replace something ask for confirmation, and
`--yes` (`-y`) skips the prompt. pltr never prompts when stdin is not a
terminal: without `--yes` such a command fails with exit code 2 and tells
you to pass `--yes`. The old `--confirm` and `--force` flags still work for
one release as deprecated aliases of `--yes`.

**Beta endpoints** work without extra flags, and their commands are labeled
`[beta]` in `--help`. `--preview` is no longer needed; where it existed it is
accepted and ignored, with a warning, for one release.

Set `PLTR_DEBUG=1` to see a Python traceback for an unexpected error.

## Every endpoint: `pltr api`

`pltr api` has a command for every method of the Foundry Platform SDK's V2
client (390 of its 394 methods; the [exceptions](docs/api-commands.md#methods-without-a-command)
are listed with their reasons). The commands are generated from the SDK, so
they mirror it one to one and follow it on every SDK upgrade:

```
pltr api <namespace> <resource> [<sub-resource>...] <method> [ARGUMENTS] [OPTIONS]
```

The curated commands above (`pltr dataset`, `pltr ontology`, ...) stay the
polished path for common tasks, with friendlier arguments and curated tables.
Use `pltr api` for an endpoint they don't cover, or when you want the API's
exact request and response shapes, for example in scripts and agents. Every
`pltr api` command follows the output, error and exit-code rules above.

```bash
pltr api --help                                   # namespaces
pltr api orchestration build --help               # a resource's methods
pltr api admin user get-current --format json
pltr api datasets dataset branch list "$DATASET_RID"
pltr api orchestration build get "$BUILD_RID"
pltr api ontologies linked-object list-linked-objects my-ontology Aircraft N123 flights
```

- **Arguments** are the endpoint's path parameters, mostly RIDs
  (`ri.foundry.main.dataset.<uuid>`); `--help` shows each one's SDK type.
  Everything else is an option named after the SDK parameter (`page_size`
  becomes `--page-size`).
- **JSON inputs**: options that take a model, a union or a dict accept JSON
  in the Foundry API's own shape (camelCase, as in Foundry's API docs),
  inline, as `@file.json` or as `@-` for stdin. The SDK validates it before
  anything is sent:

  ```bash
  pltr api admin user search --where '{"type": "queryString", "value": "jane"}'
  pltr api orchestration build search --where @filter.json --format json
  ```

- **Paging**: list endpoints print one page, in the API's response shape
  with its `nextPageToken`; `--page-token` resumes, and `--max-pages N` or
  `--all` fetch more.
- **Beta** endpoints are labeled `[beta]` and called with `preview=True` for
  you.
- **Destructive** methods (delete, remove, revoke, replace, reset, clear,
  cancel, abort, disable, undeploy, put-schema and a few others) ask for
  confirmation; `--yes` skips it.
- **Binary** responses (file content, Arrow and Parquet results, images) go
  to `--output FILE`, or to stdout when it isn't a terminal.

See **[docs/api-commands.md](docs/api-commands.md)** for the argument
mapping, paging, the destructive list and how the commands are generated.

## Using pltr from agents

pltr is built to be driven by AI agents (Claude Code, Codex, ...) and
scripts as much as by people. An agent works in four steps:

1. **Authenticate headless** with environment variables, no setup needed
   (see [Headless use](#headless-use-ci-containers-and-ai-agents)):
   `FOUNDRY_HOST` plus `FOUNDRY_TOKEN`, or `FOUNDRY_CLIENT_ID` and
   `FOUNDRY_CLIENT_SECRET`. Check with `pltr verify --format json`.
2. **Find the command** in the command manifest instead of reading every
   `--help` page. `pltr commands search` ranks commands by name,
   description and SDK method:

   ```bash
   pltr commands search list dataset branches
   pltr commands search Dataset.Branch.list
   ```

3. **Read its manifest entry**: usage, arguments, options (types, choices,
   defaults), whether it's beta, destructive or paged, its output formats and
   the SDK method it calls:

   ```bash
   pltr commands show dataset branches list --format json
   ```

4. **Run it with `--format json`** (or `PLTR_FORMAT=json`). stdout is
   exactly one JSON document; on failure, stderr's last line is a JSON error
   and the exit code says what went wrong (see
   [Output, errors and exit codes](#output-errors-and-exit-codes)).

Destructive commands never prompt without a terminal: they fail with exit
code 2 and change nothing unless you pass `--yes`.

`pltr commands list --format json` prints the whole manifest, one entry per
command, deterministically (sorted, no timestamps). The
[Claude Code skill](docs/user-guide/claude-skill.md) in `claude_skill/` packages
these rules for agents, with a command reference generated from the manifest.

## 📚 Documentation

### 📖 User Guides
- **[Quick Start Guide](docs/user-guide/quick-start.md)**: install, authenticate and run your first commands
- **[Authentication Setup](docs/user-guide/authentication.md)**: profiles, token and OAuth2, environment variables
- **[Command Reference](docs/user-guide/commands.md)**: every curated command, by group
- **[`pltr api` commands](docs/api-commands.md)**: the generated commands for every SDK method
- **[Common Workflows](docs/user-guide/workflows.md)**: multi-step tasks
- **[Pagination](docs/pagination.md)**: paging options and the paged JSON shape
- **[Command Aliases](docs/user-guide/aliases.md)**: shortcuts for long commands
- **[Claude Code skill](docs/user-guide/claude-skill.md)**: using pltr from Claude Code
- **[Troubleshooting](docs/user-guide/troubleshooting.md)**: common problems and their fixes

### 🔧 Developer Resources
- **[The command contract](docs/development/command-contract.md)**: how commands handle output, errors, confirmation and beta endpoints
- **[SDK call check](docs/development/sdk-guardrail.md)**: the CI check of every SDK call
- **[Service layer](docs/api/wrapper.md)**: architecture and how to add a command
- **[Examples Gallery](docs/examples/gallery.md)**: scripts and automation examples

### 🎯 Quick Command Overview

```bash
# Setup
pltr configure configure                  # create a profile
pltr verify                               # check authentication
pltr commands search "list dataset files" # find the command for a task

# Data
pltr sql execute "SELECT 1 AS test"       # run a SQL query
pltr ontology list                        # list ontologies
pltr dataset get <dataset-rid>            # a dataset's metadata

# Filesystem
pltr folder create "Reports" --parent-folder <project-or-folder-rid>
pltr project create "New Project" --space-rid <space-rid>
pltr resource search "sales" --folder-rid <folder-rid>
pltr resource-role grant <resource-rid> --principal-id <user-or-group-id> --role <role-id>
pltr cp <dataset-rid> <target-folder-rid>   # files and schema; --no-schema for files only

# Orchestration
pltr orchestration builds search --status FAILED --branch master
pltr orchestration jobs get <job-rid>
pltr orchestration schedules get <schedule-rid>

# Media sets
pltr media-sets get <media-set-rid> <media-item-rid>
pltr media-sets upload <media-set-rid> photo.jpg /images/photo.jpg
pltr media-sets download <media-set-rid> <media-item-rid> photo.jpg

# Connectivity
pltr connectivity connection get <connection-rid>
pltr connectivity import file <connection-rid> <dataset-rid> --name "Daily sales" --mode SNAPSHOT
pltr connectivity import execute-file <connection-rid> <file-import-rid>

# Admin
pltr admin user current
pltr admin user search jane

# Everything else
pltr api --help                           # a command for every SDK method
pltr shell                                # interactive mode
pltr completion install                   # tab completion
```

💡 **Tip**: `pltr <command> --help` lists every option of a command. Commands
that call beta Foundry endpoints say `[beta]` at the start of their help.

### 🏗️ Orchestration

```bash
# Find builds (at least one filter is required)
pltr orchestration builds search --status FAILED --branch master
pltr orchestration builds search --started-after 2026-01-31T00:00:00Z --format json

# Start a build of a dataset, follow it, cancel it
pltr orchestration builds create \
  '{"type": "manual", "targetRids": ["<dataset-rid>"]}' --branch master
pltr orchestration builds get <build-rid>
pltr orchestration builds jobs <build-rid>
pltr orchestration builds cancel <build-rid> --yes

# Jobs
pltr orchestration jobs get <job-rid>
pltr orchestration jobs get-batch <job-rid> <job-rid>

# Schedules
pltr orchestration schedules create \
  '{"target": {"type": "manual", "targetRids": ["<dataset-rid>"]}}' \
  --name "Nightly build" \
  --trigger '{"type": "time", "cronExpression": "0 2 * * *", "timeZone": "UTC"}'
pltr orchestration schedules get <schedule-rid>
pltr orchestration schedules pause <schedule-rid>
pltr orchestration schedules unpause <schedule-rid>
pltr orchestration schedules run <schedule-rid>
pltr orchestration schedules runs <schedule-rid>
pltr orchestration schedules delete <schedule-rid> --yes
```

`builds search`, `jobs get`, `jobs get-batch` and `schedules get`, `create`
and `replace` call beta endpoints and are labeled `[beta]`.

### 🎬 Media Sets

Media set RIDs look like `ri.mio.main.media-set.<uuid>` and media item RIDs
like `ri.mio.main.media-item.<uuid>`.

```bash
# A media item's metadata, its RID by path, and its media reference
pltr media-sets get <media-set-rid> <media-item-rid>
pltr media-sets get-by-path <media-set-rid> /images/photo.jpg
pltr media-sets reference <media-set-rid> <media-item-rid>

# Upload; a transactional media set needs a transaction
TXN=$(pltr media-sets create <media-set-rid> --format json | jq -r .)
pltr media-sets upload <media-set-rid> photo.jpg /images/photo.jpg "$TXN"
pltr media-sets commit <media-set-rid> "$TXN"     # or: abort ... --yes

# Download the processed or the original file (- writes to stdout)
pltr media-sets download <media-set-rid> <media-item-rid> photo.jpg
pltr media-sets download <media-set-rid> <media-item-rid> - --original > original.jpg

# Soft-delete the item at a path
pltr media-sets clear <media-set-rid> /images/photo.jpg --yes
```

### 🤖 Models

Models in the model registry, distinct from `pltr language-models` (LLM chat
and embeddings). The API can't list models, so keep the RID `model create`
prints. Creating model versions isn't supported from the CLI; use the
Python SDK.

```bash
pltr models model create "fraud-detector" --folder <folder-rid>
pltr models model get <model-rid>
pltr models version list <model-rid> --all
pltr models version get <model-rid> <model-version-rid> --format json
```

### 📊 Dataset Transactions

A transaction groups file changes so they become visible together when you
commit it, or not at all if you abort it. A branch has at most one open
transaction.

```bash
# Start a transaction (APPEND, UPDATE, SNAPSHOT or DELETE) and keep its RID
TXN=$(pltr dataset transactions start <dataset-rid> --type UPDATE --format json | jq -r .rid)

# Upload files in it
pltr dataset files upload data1.csv <dataset-rid> --transaction-rid "$TXN"
pltr dataset files upload data2.csv <dataset-rid> --transaction-rid "$TXN"

# Check it, then commit it (or abort it)
pltr dataset transactions status <dataset-rid> "$TXN"
pltr dataset transactions commit <dataset-rid> "$TXN"
pltr dataset transactions abort <dataset-rid> "$TXN" --yes

# A dataset's transactions, newest first (every branch unless --branch)
pltr dataset transactions list <dataset-rid> --branch master
```

`dataset files upload` of a directory opens and commits a transaction for
you. `--branch` defaults to the dataset's default branch.

## ⚙️ Configuration

- **Profiles**: `~/.config/pltr/profiles.json` (or `$XDG_CONFIG_HOME/pltr/`).
  Credentials are stored in the system keyring, never in this file.
- **Settings and aliases**: `settings.json` and `aliases.json` in the same
  directory.
- **Shell history**: `~/.config/pltr/repl_history` (for `pltr shell`).

pltr only creates the configuration directory when it saves something (for
example `pltr configure`); reading configuration never needs it.

| Environment variable | Effect |
|---|---|
| `PLTR_PROFILE` | Profile to use when `--profile` isn't given |
| `PLTR_FORMAT` | Default `--format`: `table`, `json` or `csv` |
| `PLTR_DEBUG=1` | Show the Python traceback of an unexpected error |
| `PLTR_KEYRING_TIMEOUT` | Seconds to wait for the system keyring (default 30) |
| `FOUNDRY_HOST`, `FOUNDRY_TOKEN`, `FOUNDRY_CLIENT_ID`, `FOUNDRY_CLIENT_SECRET` | Credentials when no profile is selected (see below) |

## 🔐 Authentication

Every command authenticates the same way, including the few that call Foundry
endpoints directly. pltr uses the **first** of these that applies:

1. `--profile NAME` on the command line
2. the `PLTR_PROFILE` environment variable (a profile name)
3. the default profile (the first profile you configure, or `pltr configure set-default NAME`)
4. environment variables, when no profile is selected by 1–3:
   - token: `FOUNDRY_HOST` and `FOUNDRY_TOKEN`
   - OAuth2 client credentials: `FOUNDRY_HOST`, `FOUNDRY_CLIENT_ID` and `FOUNDRY_CLIENT_SECRET`

An exported `FOUNDRY_*` variable never overrides, or fills gaps in, a stored
profile. `PLTR_PROFILE` naming a profile that doesn't exist is an error, not a
fallback. Hosts work with or without `https://`. `pltr verify` reports which
source it used.

### Headless use: CI, containers and AI agents

With environment variables there is nothing to set up: no `pltr configure`, no
configuration directory and no system keyring.

```bash
# Token authentication
export FOUNDRY_HOST="foundry.company.com"
export FOUNDRY_TOKEN="your-api-token"

# Or OAuth2 client credentials (used when FOUNDRY_TOKEN isn't set)
export FOUNDRY_HOST="foundry.company.com"
export FOUNDRY_CLIENT_ID="your-client-id"
export FOUNDRY_CLIENT_SECRET="your-client-secret"

pltr verify --format json   # {"authSource": {...}, "user": {...}}
```

These variables are only used when no profile is selected, so on a machine
that also has a default profile, that profile wins. `FOUNDRY_HOSTNAME` (the
Foundry SDK's name for the host) is accepted when `FOUNDRY_HOST` isn't set.

Stored profiles keep their credentials in the system keyring. If a profile is
needed and the keyring is missing, broken or doesn't answer within 30 seconds
(`PLTR_KEYRING_TIMEOUT`), pltr stops with an error that points to the
environment variables instead of hanging.

See **[Authentication Setup](docs/user-guide/authentication.md)** for complete configuration options.

## 🔧 Development

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) for dependency management

### Quick Development Setup

```bash
# Clone the repository
git clone https://github.com/anjor/pltr-cli.git
cd pltr-cli

# Install dependencies and development tools
uv sync --dev
uv run pre-commit install

# Tests, lint, format and type checks (CI runs the same)
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src/pltr
```

`uv run pytest` also runs the checks that keep pltr honest about the SDK and
its own docs: every SDK call is checked against the installed SDK's real
signatures and preview rules, the generated `pltr api` commands and the
agent skill's reference must be up to date, every command is run against
stubbed API errors to check its output contract, and every `pltr` example in
the README, `docs/` and `claude_skill/` must name real commands and options.

### Project Architecture

- **Commands** (`src/pltr/commands/`): one Typer module per command group.
  They declare their options and metadata (beta, destructive, paged, SDK
  methods) and print through `pltr.contract`.
- **Contract** (`src/pltr/contract/`): output (JSON, tables, CSV), structured
  errors and exit codes, confirmations, paging and command metadata.
- **Services** (`src/pltr/services/`): thin wrappers around
  `foundry-platform-sdk` that return SDK models.
- **Generated commands** (`src/pltr/commands/api/`): `pltr api`, generated
  from the SDK by `scripts/generate_api_commands.py`.
- **Auth and config** (`src/pltr/auth/`, `src/pltr/config/`): profiles,
  keyring access and environment-variable credentials.

Service and command tests run against a real `FoundryClient` with only HTTP
faked (the `stub_foundry_http` fixture in `tests/conftest.py`). Behaviour on
a real stack is checked with a smoke test, `uv run python scripts/smoke.py`;
**[live verification](docs/development/live-verification.md)** explains how
to run it and lists the assumptions only a live stack can confirm. See also
**[the command contract](docs/development/command-contract.md)**,
**[the SDK call check](docs/development/sdk-guardrail.md)** and
**[the service layer guide](docs/api/wrapper.md)**.

## 📊 Status

pltr is published on [PyPI](https://pypi.org/project/pltr-cli/) as
`pltr-cli`. It is 0.x: a minor release can contain breaking changes, and
[CHANGELOG.md](CHANGELOG.md) lists each one. Tests run against the real SDK
with stubbed HTTP; behaviour against a live Foundry stack is checked on a
best-effort basis.

## 🤝 Contributing

Contributions are welcome: bug fixes, new commands and documentation.

1. Fork the repository and create a branch.
2. Make your change following [the command contract](docs/development/command-contract.md):
   new commands go through `foundry-platform-sdk`, label beta endpoints, and
   ask before destructive operations.
3. Add tests that use `stub_foundry_http`.
4. Record user-visible changes under `## [Unreleased]` in
   [CHANGELOG.md](CHANGELOG.md), and update the README and `docs/`.
5. Run the checks above and open a pull request. Say in it what you verified
   on a live stack (paste the smoke test's table if you ran it) and which
   assumptions you couldn't check.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

Built on top of the official [Palantir Foundry Platform Python SDK](https://github.com/palantir/foundry-platform-python).
