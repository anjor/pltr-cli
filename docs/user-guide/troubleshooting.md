# Troubleshooting Guide

Common problems with pltr and how to fix them.

## Quick Diagnostics

```bash
pltr --version                  # is pltr installed, and which version?
pltr verify --format json       # which credentials, and do they work?
pltr configure list-profiles    # which profiles exist, and which is the default?
```

## Reading an Error

Every command reports failures the same way. The exit code says what kind of
failure it was:

| Exit code | Meaning | What to check |
|---|---|---|
| 1 | Unexpected error, or "no" at a prompt | Re-run with `PLTR_DEBUG=1` for the traceback, and report it |
| 2 | Usage error | The arguments: the message names the problem; see `pltr <command> --help` |
| 3 | Authentication | The credentials (see below) |
| 4 | Permission denied (HTTP 403) | Your access to the resource, or the OAuth client's scopes |
| 5 | Not found (HTTP 404) | The RID, and that you can see the resource |
| 6 | Validation error (HTTP 400, 422) | The values you sent; the message has Foundry's error name |
| 7 | Other API or network errors | Connectivity, rate limits (429), server errors |

In text mode the error is printed as `Error: ...` on stderr, with Foundry's
error name and parameters. With `--format json` (or `PLTR_FORMAT=json`), the
last line of stderr is a JSON object:

```bash
pltr dataset get <dataset-rid> --format json 2> error.json || tail -n 1 error.json
# {"type": "not_found", "message": "DatasetNotFound: ...", "exitCode": 5,
#  "statusCode": 404, "errorName": "DatasetNotFound", ...}
```

`PLTR_DEBUG=1` prints the Python traceback of an unexpected error.

## Authentication

### Which credentials does pltr use?

`pltr verify --format json` shows it under `authSource`. pltr uses the first
of: `--profile`, `PLTR_PROFILE`, the default profile, then the `FOUNDRY_*`
environment variables. Environment variables are ignored when a profile is
selected, including the default profile, so on a machine with a default
profile `FOUNDRY_TOKEN` has no effect. See [Authentication](authentication.md).

### "Authentication failed (HTTP 401)" (exit code 3)

The token expired, was revoked or belongs to another stack. Create a new
token and store it:

```bash
pltr configure configure --profile your-profile --host foundry.company.com --token "$NEW_TOKEN" --yes
pltr verify --profile your-profile
```

Hosts work with or without `https://`.

### "Permission denied (HTTP 403)" from `pltr verify` (exit code 4)

The credentials work, but they may not read the current user: an OAuth
client needs the `api:admin-read` scope for `pltr verify`. Other commands
need their own scopes.

### "Profile 'x' not found"

`--profile` or `PLTR_PROFILE` names a profile that doesn't exist; pltr
doesn't fall back to the default profile. Check the name with
`pltr configure list-profiles`, or unset `PLTR_PROFILE`.

### "No profile specified and no default profile configured"

Nothing is configured. Run `pltr configure configure`, or export
`FOUNDRY_HOST` and `FOUNDRY_TOKEN` (or `FOUNDRY_CLIENT_ID` and
`FOUNDRY_CLIENT_SECRET`).

### Keyring errors, or pltr waits at start

Profiles keep their credentials in the system keyring. In containers, CI
and SSH sessions the keyring may be missing or unable to show its unlock
prompt; pltr gives up after 30 seconds with an error that points to the
environment variables.

- Use environment variables instead, with no profile selected.
- If the keyring only needs longer (for example while you type a keychain
  password), set `PLTR_KEYRING_TIMEOUT=120` (`0` waits indefinitely).
- On Linux without a desktop keyring, install a backend for the
  [keyring](https://pypi.org/project/keyring/) package.

## Scripts, CI and Agents

### "Confirmation is required, but stdin is not a terminal. Re-run with --yes to proceed." (exit code 2)

Destructive commands (delete, remove, revoke, reset, cancel, abort,
replace, ...) ask before they change anything, and never prompt without a
terminal. Pass `--yes` (`-y`) once you're sure:

```bash
pltr dataset branches delete <dataset-rid> old-branch --yes
```

### A deprecation warning about `--confirm`, `--force` or `--preview`

These flags still work in this release and will be removed in the next one.
Use `--yes` instead of `--confirm`/`--force`; drop `--preview` (beta
endpoints no longer need it). On `resource delete`,
`resource permanently-delete`, `configure delete` and
`data-health check delete`, `-f` now means `--format`.

### Invalid JSON input (exit code 2)

Options that take JSON accept it inline, as `@file.json` or as `@-` (stdin).
Use single quotes in the shell. The error names the location of the
problem, for example `at value[1].value (type 'gt'): required field
missing`.

```bash
pltr ontology action-apply <ontology> myAction '{"param": "value"}'
pltr ontology action-apply <ontology> myAction @params.json
```

### Only part of a list comes back

List commands fetch one page by default. Pass `--all` for every page, or
`--page-token` with the `nextPageToken` from the previous JSON output. See
[Pagination](../pagination.md).

### JSON parsing fails on pltr's output

stdout carries exactly one JSON document with `--format json`; messages go
to stderr. Don't merge the streams (`2>&1`) when you parse stdout.

## Data Access

### "Invalid RID" (exit code 2) or "not found" (exit code 5)

RIDs look like `ri.foundry.main.dataset.<uuid>`: copy them from Foundry's
web interface, or find them with `pltr resource get-by-path "/Space/Project/name"`
or `pltr folder list <folder-rid>`. A 404 can also mean you can't see the
resource. User and group IDs are UUIDs, not usernames: find them with
`pltr admin user search` and `pltr admin group search`.

### SQL queries

- Refer to datasets by path or RID in backticks, inside single quotes:
  ``pltr sql execute 'SELECT * FROM `<dataset-rid>` LIMIT 10'``.
- A query that fails exits with code 7, and the error has Foundry's message.
- `--timeout` exits with code 7 and leaves the query running. For long
  queries, submit and wait:

  ```bash
  QUERY_ID=$(pltr sql submit 'SELECT * FROM `<dataset-rid>`' --format json | jq -r .queryId)
  pltr sql wait "$QUERY_ID" --timeout 3600
  ```

- `pltr sql results` exits with code 6 while the query is still running.

## Installation

### "command not found: pltr"

The directory your installer puts scripts in isn't on `PATH`. The isolated
installs manage that for you:

```bash
uv tool install pltr-cli      # or: pipx install pltr-cli
uv tool update-shell          # adds uv's tool directory to PATH
```

### A `pltr api` command fails because of the installed SDK

`pltr api` commands are generated from one foundry-platform-sdk version. If
another package upgraded or downgraded the SDK in the same environment, a
command whose SDK method changed fails with exit code 1 and names both
versions. Install pltr in its own environment (`uv tool install pltr-cli` or
`pipx install pltr-cli`).

## Shell and Completion

### Tab completion doesn't work

```bash
pltr completion install       # detects your shell; or --shell bash|zsh|fish
exec "$SHELL"                 # start a new shell

# Or load the script yourself
pltr completion show --shell bash >> ~/.bashrc
```

### `pltr shell`

Type commands without the `pltr` prefix; `help [command]`, `exit` and
`quit` work, and aliases are expanded. History is saved in
`~/.config/pltr/repl_history`. With stdin from a file or a pipe, the shell
runs the commands line by line without a prompt.

## Getting Help

```bash
pltr --help                     # command groups
pltr dataset --help             # a group's commands
pltr dataset files get --help   # a command's arguments and options
pltr commands search "download a file"
```

When reporting a problem, include `pltr --version`, the command you ran, and
the error (with `--format json`, the last stderr line).
