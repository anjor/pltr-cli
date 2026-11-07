### Breaking

- **`widgets`, `aip-agents`, `third-party-apps` and `verify` follow the output
  and error contract.** `--format json` prints the SDK's own serialization
  (Foundry API field names in camelCase, null fields left out) instead of
  snake_case keys with nulls; lists print `{"data": [...], "nextPageToken":
  "..."}`. Status messages go to stderr. Errors are structured and use the
  documented exit codes (2 usage, 3 auth, 4 permission denied, 5 not found,
  6 validation, 7 other API/network errors); they all used to exit with 1.
- **Removed `pltr widgets dev-mode get`, `disable` and `pause`.** They called
  `DevModeSettings.get/disable/pause`, which the SDK doesn't have, so they
  always failed. **`widgets dev-mode enable` is removed too**: with no way to
  read, pause or disable dev mode through the API, a `dev-mode` group that can
  only switch it on would be confusing. Use the generated commands instead:
  `pltr api widgets dev-mode-settings enable` (or `set-widget-set-by-id`) and
  `pltr api widgets dev-mode-settings-v2 enable` (or `set-widget-set-manifest`).
- **`widgets release list` fetches one page by default** (it fetched every
  page). Use `--all`, `--max-pages N` or `--page-token`.
- **`widgets release delete` no longer prompts when stdin is not a terminal**:
  without `--yes`/`-y` it fails with exit code 2. Answering "no" now exits
  with code 1 (was 0). The prompt goes to stderr.
- **Table and CSV columns** of these commands read real model fields:
  - `widgets get`: RID, publish repository; `widgets release list/get`:
    version, description, widget set, repository, repository version;
    `widgets repository get`: RID, widget set.
  - `aip-agents get`: RID, version, display name, description, input
    placeholder, suggested prompts, parameters (`id (type, access)`);
    `sessions list/get`: RID, title, (agent,) agent version, message count,
    created, updated and estimated expiry time; `versions list`: version,
    major, minor.
  - `third-party-apps get`: RID (the API returns nothing else).
- **`pltr verify`**: error `type` values use the contract's names
  (`auth_error`, `permission_denied`, `not_found`, `network_error`,
  `server_error`, ...; they were `auth`, `permission_denied`, `not_found`,
  `api`, `unexpected`), and the error JSON carries `errorCode`/`errorName`/
  `errorInstanceId`/`parameters` like every other command. An invalid
  `PLTR_FORMAT` is now a usage error (exit 2), as for every command; verify
  used to ignore it. Output (`{"authSource": {...}, "user": {...}}`, the
  table and CSV columns) is unchanged.
- **`pltr configure configure` never prompts when stdin is not a terminal.**
  Missing values are a usage error (exit 2) that names the options to pass.
  Replacing an existing profile asks first; non-interactively it needs
  `--yes`/`-y` (exit 2 otherwise). Answering "no" exits with 1 (was 0).
  `--auth-type` only accepts `token` or `oauth` (it stored any value), and
  credentials of the other auth type (e.g. `--client-id` with `--auth-type
  token`) are rejected instead of silently dropped. Prompts go to stderr.
- **`pltr configure delete`** asks unless `--yes`/`-y` and needs `--yes` when
  stdin is not a terminal. `--force` is a hidden deprecated alias of `--yes`;
  **`-f` now means `--format`** (it was `--force`). An unknown profile exits
  with 5 (`not_found`; was 1). A profile whose keyring entry is already gone
  is now removed (with a warning) instead of failing.
- **`pltr configure set-default`**: an unknown profile exits with 5
  (`not_found`; was 1).
- **`pltr alias`**:
  - `remove`, `clear`, and `import` replacing existing aliases ask unless
    `--yes`/`-y`, and need `--yes` when stdin is not a terminal (exit 2).
    Answering "no" exits with 1 (was 0).
  - An unknown alias exits with 5 (`not_found`) for `show`, `edit`, `remove`
    and `resolve`; `show` and `resolve` used to print a message and exit 0.
  - Name clashes without `--force`, reserved names, circular references and
    bad import files are usage errors (exit 2; was 1).
  - An alias can't take the name of any top-level pltr command (the reserved
    list was a subset: `folder`, `space`, `api` and others were allowed and
    would have shadowed the command).
  - `list`, `show` and `resolve` print tables (or JSON/CSV with `--format`);
    `show` and `resolve` printed `name → command` lines.
  - All messages go to stderr; `export` prints `{}` when there are no aliases
    (it printed a message to stdout).
- **`pltr completion show` prints the bare script** on stdout (it printed a
  Rich panel with line numbers). Messages and activation instructions of
  `install`/`uninstall` go to stderr. An unsupported `--shell` or an
  undetectable shell is a usage error (exit 2; was 1).
- **`pltr shell` banner and "Goodbye!" go to stderr**, and only when stdin is
  a terminal.

### Added

- `[beta]` labels on every `widgets`, `aip-agents` and `third-party-apps`
  command (all their endpoints are beta).
- `--page-token` on `widgets release list`, `aip-agents sessions list` and
  `aip-agents versions list`; `--max-pages` and `--all` on `widgets release
  list`; `--branch` on `widgets release list` (the SDK's branch filter).
- `--format` on `widgets release delete`, every `configure` command, and
  `alias add/remove/edit/list/show/clear/import/resolve` (on `alias add` only
  the long `--format`, since `-f` is `--force` there); `--output` on
  `verify`, `configure list-profiles` and `alias list/show/resolve`.
- `configure list-profiles --format json`: `{"data": [{"name": ...,
  "default": true|false}]}`. `alias list --format json`: `{"data": [{"name":
  ..., "command": ...}]}`; `alias show/resolve --format json`: `{"name": ...,
  "command": ...}`.
- `configure configure` infers `--auth-type` from `--token` or
  `--client-id`/`--client-secret`.
- `pltr shell` expands aliases, completes alias names, and accepts `help
  [command]`, `exit`/`quit`, `!command` and `# comments`. With stdin that
  isn't a terminal it runs commands line by line (`pltr shell < commands.txt`).

### Changed

- `aip-agents get/sessions/versions` and `third-party-apps get` always call
  their beta endpoints with `preview=True`.
- `pltr verify` uses the shared output and error layer; its failure messages
  keep their guidance (rejected credentials, the `api:admin-read` scope, an
  unreachable host, the OAuth token endpoint's answer) as context of the
  structured error.
- `pltr shell` no longer uses click-repl's `repl()` (prompt_toolkit is still
  used); each line runs as its own `pltr` invocation.

### Deprecated

- `third-party-apps get --preview`: hidden no-op with a warning.
- `configure delete --force`: hidden alias of `--yes` with a warning.
- `alias remove/clear --no-confirm`: hidden alias of `--yes` with a warning;
  `--confirm` (the old default) is a hidden no-op with a warning.

### Removed

- `pltr widgets dev-mode get`, `disable`, `pause` and `enable` (see Breaking).
- `AliasManager.display_aliases` (it printed to stdout; the alias commands
  use the shared output layer).

### Fixed

- `third-party-apps get` failed unless `--preview` was given (#184).
- `pltr shell` failed on click 8.2: it printed an empty error box at start,
  and click-repl's `repl()` crashed on the first command (it assigns
  `ctx.protected_args`, read-only in click 8.2).
- `pltr completion install/show` scripts never completed anything: they used
  click's completion protocol (`_PLTR_COMPLETE=bash_complete`), but the `pltr`
  executable is a Typer app that answers Typer's protocol (`complete_bash`)
  and replied "Shell complete not supported." The scripts are now generated
  by Typer (bash, zsh, fish) and complete commands, options, option values
  and the `pltr api` tree. The zsh script also completes on the first TAB when
  autoloaded from `fpath` (where `install` puts it).
- `widgets release list` passed its arguments through a `**kwargs` dict that
  the SDK-call guardrail couldn't check.

### Docs to update

- `README.md`: the exit-code/contract section can now list `widgets`,
  `aip-agents`, `third-party-apps`, `verify` and the local commands as
  converted; `pltr third-party-apps get <rid>` is beta and returns only the
  RID.
- `docs/user-guide/commands.md`: `configure delete` (`--yes/-y`, `-f` is
  `--format`, `--force` deprecated; example `--force` → `--yes`); `completion
  show` prints the bare script (`eval "$(pltr completion show --shell bash)"`
  works); the `shell` section (help/exit words, alias expansion, batch mode
  from stdin); add `widgets`, `aip-agents` and `third-party-apps` sections if
  missing, without `widgets dev-mode`.
- `docs/user-guide/authentication.md` (lines ~287-331) and
  `claude_skill/reference/quick-start.md` (~80): `configure delete
  old-profile --force` → `--yes`.
- `docs/user-guide/troubleshooting.md` (~349): "Ensure click-repl is
  installed" no longer applies; `pltr completion show --shell bash >>
  ~/.bashrc` now appends a valid script.
- `claude_skill/reference/aip-agents-commands.md` and `claude_skill/SKILL.md`:
  agent RIDs look like `ri.aip-agents..agent.<id>` (not
  `ri.foundry.main.agent.abc123`); every command is `[beta]`; add
  `--page-token`; JSON is camelCase SDK output with the paged shape.
- `pyproject.toml`: pltr no longer imports `click_repl`; the dependency could
  become `prompt-toolkit` (which click-repl brings in today).
- **Aliases don't work with the `pltr` executable** (only with `python -m
  pltr`, and now in `pltr shell`): the console script `pltr =
  "pltr.cli:app"` skips `pltr/__main__.py`, where `inject_alias_resolution()`
  runs. Fix (shared files): point the console script at a `main()` that calls
  `inject_alias_resolution()` and then `app()`, and drop `__main__.py`'s own
  `_PLTR_COMPLETE` block, which answers click's protocol and would break the
  new Typer-protocol completion scripts. Then remove the "Alias Not Working"
  note 3 from `docs/user-guide/aliases.md`.

### Not verified live

- Example RID formats in help texts (`ri.aip-agents..agent.<id>`,
  `ri.aip-agents..session.<id>`,
  `ri.third-party-applications.main.application.<id>`,
  `ri.widgetregistry..widget-set.<id>`, `ri.stemma.main.repository.<id>`)
  come from the API documentation, not a live stack.
- That the Widgets, AIP Agents and Third Party Applications endpoints accept
  `preview=true` on a live stack (the SDK marks them beta; pltr always sends
  it).
- `widgets release list --branch` (the SDK's `branch` query parameter) and
  the response shapes used in tests (built from the SDK models).
- Completion scripts were verified end to end in bash only; zsh and fish were
  checked by running their protocol against the app, not in a real zsh or
  fish.
