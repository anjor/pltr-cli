### Added

- `pltr api`: a generated command for every callable method of the Foundry
  Platform SDK V2 client (390 commands in 18 namespaces for foundry-platform-sdk
  1.111.0), mirroring the SDK as
  `pltr api <namespace> <resource> [<sub-resource>...] <method>` (#186). Covers
  #145: `orchestration build` and `orchestration job` are reachable.
  - Path parameters are positional arguments; other parameters are options;
    models, unions and dicts take JSON inline, from `@file.json` or from `@-`
    (stdin); `bytes` bodies take `--body FILE` or `--body -`.
  - The commands follow the shared output, error and exit-code contract (#187)
    and have its shared options: `--profile/-p`, `--format/-f table|json|csv`
    (default from `PLTR_FORMAT`), `--output/-o`, `--yes/-y` on destructive
    commands, and `--page-size`, `--page-token`, `--max-pages` and `--all` on
    paged commands. JSON output is the SDK's own serialization (camelCase API
    field names, nulls left out); a call with no response body prints `null`.
  - Paged commands print one page exactly as the API returns it (with its
    `nextPageToken` and fields such as `totalCount`); `--max-pages`/`--all` print
    the merged items as `{"data": [...], "nextPageToken": ...}`.
  - Beta endpoints (203 commands) are labeled `[beta]` and called with
    `preview=True` automatically, only if the installed SDK method still takes
    `preview`.
  - Destructive methods (58, an explicit reviewed list) ask for confirmation;
    `--yes`/`-y` skips it; without a terminal on stdin they fail with exit code 2
    (`confirmation_required`).
  - Binary responses (20 commands) stream to `--output FILE`, or to stdout when it
    is not a terminal.
  - Every generated command records its `CommandMeta` (SDK method, beta,
    destructive, paged), so `pltr.contract.iter_commands` lists the whole tree for
    the manifest (#188).
  - Commands load lazily: `pltr --help` imports none of the generated specs.
- `pltr.contract` (#187 layer): `emit_bytes` and `check_binary_output` for binary
  responses; `emit` shows a paged response model (e.g. `ListObjectsResponseV2`) as
  one row per item in tables and CSV while JSON keeps the whole response; and
  `load_json_input` accepts `@-` for stdin.
- `scripts/generate_api_commands.py` regenerates the specs from the installed SDK;
  a test fails when the committed specs are stale.
- `scripts/coverage.py` reports, per SDK method, the generated command and the
  curated commands that reach it (read from `CommandMeta`), and asserts that every
  callable V2 method has a generated command.
- `docs/api-commands.md` documents the `pltr api` tree; the README has a `pltr api`
  section and recommends an isolated install (`uv tool install pltr-cli` /
  `pipx install pltr-cli`).

### Changed

These describe how `pltr api` changed while it was built (it hasn't been released
before), for reviewers of the earlier version on this branch:

- Output, errors, exit codes and confirmation now come from `pltr.contract`
  instead of a module of its own. Error types follow the shared set:
  `auth_error` (was `authentication_error`), `conflict`, `request_too_large`,
  `rate_limited`, `server_error`, `network_error` and `timeout` (were all
  `api_error`), `confirmation_required` (was `usage_error`) for a destructive
  command without `--yes` and no terminal, `aborted` (was `cancelled`), and
  `unexpected_error` with an install hint (was `sdk_unavailable`) when the
  installed SDK lacks a method or parameter.
- Binary commands write to the shared `--output/-o FILE`; `--output-file` is gone.
- Paged commands gained `--max-pages`; their `--page-size` now rejects values
  below 1 before calling the API.
- The confirmation prompt reads `Run <METHOD> <path> (FoundryClient....)? [y/N]`,
  and the prompt for a destructive command now comes after authentication.
- A group run without a subcommand in JSON mode shows click's help again (the
  contract's choice) instead of a JSON error listing the subcommands.
- Results that aren't SDK models (such as the `dict[str, Long]` of
  `streams dataset stream subscriber get-read-position`) print the decoded values
  (numbers) instead of the SDK's string form of `Long`.
- In table mode a call with no response body prints a "Done" message on stderr,
  and a string result is shown as a one-row table.

### Removed

- `pltr api media-sets media-set tile` and
  `pltr api models model-studio config-version get`: foundry-platform-sdk 1.111.0
  can't call `MediaSet.tile` or `ModelStudio.ConfigVersion.get`, because it
  URL-quotes path parameters with `urllib.parse.quote`, which raises for their
  integer path parameters before any request is sent. They are excluded, with this
  reason, until the SDK handles integer path parameters.

### Docs to update

- docs/user-guide/commands.md and the Claude skill (`claude_skill/`): mention
  `pltr api` for endpoints without a curated command (the skill should be generated
  from the manifest in #188).
- CI (`.github/workflows/ci.yml`): optionally run `uv run python scripts/coverage.py`
  so the coverage table shows in the logs; the pytest suite already enforces the
  generated coverage and fresh specs.
- A curated `media-sets` command that calls `MediaSet.tile` (if any) hits the same
  SDK bug as the excluded generated command.

### Not verified live

- Every generated command was tested only against stubbed HTTP with a real
  `FoundryClient`: one command per namespace plus paging, beta, destructive, binary
  and upload cases, and the CLI contract test runs all 390 against 404 and 400
  responses. None was run against a live Foundry stack.
- Streaming endpoints that the SDK returns as bytes (for example
  `aip-agents agent session streaming-continue`, `ontologies time-series-property-v2
  stream-points`) are written to the output as they arrive; their formats are not
  verified live.
- `--max-pages`/`--all` assume paged endpoints accept the returned `nextPageToken`
  with the same other arguments (the SDK's own iterator does the same).
- Sending `[]` for a required list parameter that was left out (for example `select`
  in `ontologies ontology-object search`, meaning all properties) is assumed to be
  accepted by each endpoint; the help says so, and the API validates it.
- `ontologies attachment upload`: the SDK sends `Content-Type: */*` whatever
  `--content-type` says (a duplicate key in the SDK's header dict); pltr passes the
  value through unchanged.
