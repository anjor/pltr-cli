### Breaking

- **Status output moved to stderr, for every command.** Success, info,
  warning and error messages printed through pltr's shared formatter
  (`OutputFormatter.print_*`), spinners and progress bars now go to stderr;
  they used to go to stdout. stdout is reserved for data. With
  `--format json`, informational messages are suppressed, and warnings and
  errors are printed as JSON Lines (`{"type": "warning"|"error", ...}`).
  Scripts that parsed status text from stdout must read stderr.
- **`folder` and `space`: `--format json` prints the SDK's own
  serialization.** Field names are the Foundry API's (camelCase, for example
  `displayName`, `parentFolderRid`, `createdTime`), null fields are left out,
  and the invented `"type": "folder"`/`"type": "space"` keys are gone.
  `folder list` and `space list` print `{"data": [...], "nextPageToken":
  "..."}`. `folder batch-get` prints the API response,
  `{"data": {"<folder RID>": {...}}}`. `space delete --format json` prints
  `null`.
- **`folder` and `space` exit codes:**

  | Code | Meaning |
  |---|---|
  | 2 | usage error |
  | 3 | authentication |
  | 4 | permission denied |
  | 5 | not found |
  | 6 | validation |
  | 7 | other API or network error |

  Every error used to exit with 1. Errors are structured; see the README
  section "Output, errors and exit codes".
- **`folder list` and `space list` fetch one page by default**; they used to
  fetch every page. Use `--all`, `--max-pages N`, or `--page-token` with the
  `nextPageToken` of an earlier response. This matches the other paginated
  commands.
- **`space delete` no longer prompts when stdin is not a terminal.** Without
  `--yes`/`-y` it fails with exit code 2. Interactive prompts are written to
  stderr.
- **Table and CSV columns of `folder` and `space` changed.** They now show
  real model fields:
  - `folder`: path, project, space, trash status, created/updated time and
    by.
  - `space`: path, organizations, deletion-policy organizations, default
    role set, usage account, file system.

  The old columns read fields that don't exist and were always empty.
- **`folder` and `space` validate `--format`/`-f`:** only table, json and
  csv are accepted (case-insensitive). Any other value used to fall back to
  a table.

### Added

- `PLTR_FORMAT` environment variable: the default `--format` for every
  converted command (`folder`, `space`).
- `PLTR_DEBUG=1` shows the Python traceback of an unexpected error. Unexpected
  errors are otherwise printed as one `Error: ...` line, also for commands
  that haven't been converted yet.
- `--page-size`, `--page-token`, `--max-pages` and `--all` on `folder list`
  and `space list`.
- `--output`/`-o` on `folder create`, `space create` and `space update`.
- `-p` as the short form of `--profile` on `folder get`, `folder list`,
  `folder batch-get` and every `space` command. `folder create` keeps `-p`
  for `--parent-folder`.
- `space create --default-role-set-id`, `--file-system-id` and
  `--usage-account-rid`.
- `space update --default-role-set-id` and `--usage-account-rid`.
- `[beta]` label in the help of `space create`, `get`, `update` and
  `delete`: they call beta Foundry endpoints, always with `preview=true`.
- For developers: the `pltr.contract` package (output, structured errors,
  exit codes, confirmation, command metadata). It is documented in
  `docs/development/command-contract.md`. A CLI-wide contract test,
  `tests/test_contract/test_cli_contract.py`, has per-module allowlists of
  commands that haven't been converted yet.

### Changed

- `space update` now reads the space and sends back the current values of
  the fields you don't change. `Space.replace` resets omitted optional
  fields: the description was cleared, and the default role set and usage
  account fell back to the enrollment's defaults.
- Python warnings raised while a converted command runs (for example SDK
  `UserWarning`s) are printed as `Warning: ...` on stderr, or as a JSON
  warning line in JSON mode.
- Parse-time usage errors (a missing argument, an unknown option) are
  printed as a JSON error object when the invocation asked for JSON
  (`--format json` or `PLTR_FORMAT=json`).
- `folder create --parent-folder` help now says that folders can only be
  created inside a project.

### Deprecated

- `space delete --confirm`: a hidden alias of `--yes` that prints a
  deprecation warning. It will be removed in the next release.

### Removed

- `space list --organization-rid`/`-org`. The SDK's `Space.list` has no
  organization filter, and the option never worked: the call was rejected.
  It stays as a hidden option for one release; using it exits with code 2
  and explains how to filter the JSON output on `organizations` instead.

### Fixed

- `folder get`, `folder create` and `folder batch-get` printed empty
  created/modified values because they read fields `Folder` doesn't have
  (#183).
- `folder batch-get` always failed: the response has `data` (a map of RID
  to folder), not `folders`.
- `space create` always failed: it passed `default_roles`/`role_grants`,
  which `Space.create` doesn't accept (#182).
- `space get`, `list`, `create` and `update` printed empty values for
  `organization_rid`, `root_folder_rid`, `created_by` and other fields
  `Space` doesn't have.
- `folder create`, `get`, `list` and `batch-get` and `space list` no longer
  pass `preview=` to GA endpoints, so the SDK warning is gone (#184).
- `pltr cp`: copying folders now works with folder service results that are
  SDK models, and still copies every page of a folder's children.

### Docs to update

- `README.md` quick start and command overview:
  - `pltr folder create "My Project"` lacks the required `--parent-folder`.
  - `pltr space create "Team Space" <org-rid>` is not valid; it needs
    `--enrollment-rid`, `--organization` and `--deletion-policy-org`.
- `docs/user-guide/commands.md`, `folder` and `space` sections:
  - JSON is now camelCase in the paged shape;
  - list commands fetch one page by default and take the paging options;
  - `space delete` needs `--yes` when not interactive;
  - `--organization-rid` was removed;
  - the new `space create`/`update` flags;
  - new exit codes.
- `docs/pagination.md`: `folder list` and `space list` now support the
  standard paging flags. Converted commands print `{"data": [...],
  "nextPageToken": ...}`, not `{"data": [...], "pagination": {...}}`.
- `claude_skill/`: describe the JSON, stderr and exit-code contract and
  `PLTR_FORMAT`, and update the folder/space examples.
- `CHANGELOG.md`: fold this fragment into the release notes.

### Not verified live

- `Space.replace` resetting omitted optional fields is taken from the SDK
  docstrings ("If not provided, the default ... will be used"). Sending the
  current `defaultRoleSetId`/`usageAccountRid` back unchanged is assumed to
  be accepted, with no extra permission needed.
- `folder list ri.compass.main.folder.0` (children of the root folder) is
  kept as a documented example from earlier releases.
- The OAuth token-failure mapping (exit 3) follows the SDK's behaviour:
  `SDKInternalError` caused by an `httpx.HTTPStatusError` for
  `.../oauth2/token`. It was reproduced with a faked HTTP layer, not
  against a real stack.
- Typed SDK errors drop the response's `errorCode`. pltr derives it from
  the HTTP status (400 INVALID_ARGUMENT, 401 UNAUTHORIZED, 403
  PERMISSION_DENIED, 404 NOT_FOUND, 409 CONFLICT, 413
  REQUEST_ENTITY_TOO_LARGE) and leaves it out for 422 and 5xx. A real
  stack could use a different code for some typed errors.
