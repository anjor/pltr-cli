### Added

- `pltr api`: a generated command for every public method of the Foundry Platform
  SDK V2 client (392 commands in 18 namespaces for foundry-platform-sdk 1.111.0),
  mirroring the SDK as `pltr api <namespace> <resource> [<sub-resource>...] <method>`
  (#186). Covers #145: `orchestration build` and `orchestration job` are reachable.
  - Path parameters are positional arguments; other parameters are options; models,
    unions and dicts take JSON inline, from `@file.json` or from `@-` (stdin);
    `bytes` bodies take `--body FILE` or `--body -`.
  - `--profile`, `--format table|json|csv` (default from `PLTR_FORMAT`) and
    `--output`. JSON output is the SDK's own serialization (camelCase API field
    names, nulls left out); paged endpoints print one page in the API's shape with
    its `nextPageToken`, and `--all` fetches every page.
  - Beta endpoints (205) are labeled `[beta]` and called with `preview=True`
    automatically, only if the installed SDK method still takes `preview`.
  - Destructive methods (58, an explicit reviewed list) ask for confirmation;
    `--yes`/`-y` skips it; without a terminal on stdin they fail with exit code 2.
  - Binary responses (21) stream to `--output-file`, or to stdout when it is not a
    terminal.
  - Exit codes 0-7 and, in JSON mode, one compact JSON error object on stderr.
  - Commands load lazily: `pltr --help` imports none of the generated specs.
- `scripts/generate_api_commands.py` regenerates the specs from the installed SDK;
  a test fails when the committed specs are stale.
- `scripts/coverage.py` reports which SDK methods pltr commands reach (all 394 V2
  methods except two server-sent-events methods, `functions.Query.streaming_execute`
  and `functions.Query.streaming_execute_events`, which are excluded with a reason).
- `docs/api-commands.md` documents the `pltr api` tree.

### Docs to update

- README.md: document the `pltr api` tree, how it relates to the curated commands,
  and recommend an isolated install (`uv tool install pltr-cli` /
  `pipx install pltr-cli`) so the SDK version is the one pltr was tested with
  (#186 acceptance). Link `docs/api-commands.md`.
- README.md: document the exit codes 0-7 (shared with #187).
- docs/user-guide/commands.md and the Claude skill (`claude_skill/`): mention
  `pltr api` for endpoints without a curated command (the skill should be generated
  from the manifest in #188).
- CI (`.github/workflows/ci.yml`): optionally run `uv run python scripts/coverage.py`
  so the coverage table shows in the logs; the pytest suite already enforces 100%
  coverage and fresh specs.

### Not verified live

- Every generated command was tested only against stubbed HTTP with a real
  `FoundryClient` (one command per namespace plus paging, beta, destructive, binary
  and upload cases), not against a live Foundry stack.
- Streaming endpoints that the SDK returns as bytes (for example
  `aip-agents agent session streaming-continue`, `ontologies time-series-property-v2
  stream-points`) are written to the output as they arrive; their formats are not
  verified live.
- `--all` assumes paged endpoints accept the returned `nextPageToken` with the same
  other arguments (the SDK's own iterator does the same).
- Sending `[]` for a required list parameter that was left out (for example `select`
  in `ontologies ontology-object search`, meaning all properties) is assumed to be
  accepted by each endpoint.
- `ontologies attachment upload`: the SDK sends `Content-Type: */*` whatever
  `--content-type` says (a duplicate key in the SDK's header dict); pltr passes the
  value through unchanged.
