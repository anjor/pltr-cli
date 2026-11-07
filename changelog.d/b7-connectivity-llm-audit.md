### Breaking

- **`connectivity`, `language-models` and `audit`: `--format json` prints the
  SDK's own serialization.** Field names are the Foundry API's (camelCase),
  null fields are left out, and lists print as `{"data": [...],
  "nextPageToken": "..."}`:
  - `connectivity connection get`, `create` and `upload-jdbc-drivers` print
    the `Connection` (`configuration`, `worker`, `exportSettings`, ...),
    not pltr's flat dict with `connection_type`, `status`, `created_time`
    and `modified_time` (fields a connection doesn't have; they were always
    `N/A`). `upload-jdbc-drivers` prints the connection after the last
    upload, not a list with one entry per file.
  - `connection get-config` prints the configuration itself, not
    `{"connection_rid": ..., "configuration": ...}`.
  - `import file`, `table`, `get-file` and `get-table` print the
    `FileImport`/`TableImport`; `list-file` and `list-table` print the paged
    shape.
  - `language-models anthropic messages` and `messages-advanced` print the
    API's `AnthropicMessagesResponse` (`content`, `stopReason`,
    `usage.inputTokens`, ...), and `openai embeddings` its
    `OpenAiEmbeddingsResponse` (`data` is a list of vectors,
    `usage.promptTokens`), instead of snake_case keys with nulls.
  - `language-models list` prints `{"data": [...]}` with each model object
    as the endpoint returned it; `status` prints that object and `enroll` the
    endpoint's response body (`null` when it has none). They used to print
    pltr's `model_rid`, `status`, `type` and `display_name`, filled in with
    invented values (`AVAILABLE`, `AVAILABLE_VIA_PROXY`, `ENROLLED`,
    `OPENAI`, `UNKNOWN`) where the endpoint didn't say.
  - `audit list` prints `{"data": [{"id": ...}], "nextPageToken": ...}`.
- **The default format is `table`** for `connectivity connection
  get-config`, `language-models anthropic messages`, `anthropic
  messages-advanced` and `openai embeddings`; they defaulted to JSON. Pass
  `--format json`, or set `PLTR_FORMAT=json`.
- **Exit codes for these commands:** 2 usage error, 3 authentication, 4
  permission denied, 5 not found, 6 validation, 7 other API or network
  error. Every error used to exit with 1. Errors are structured (with
  `--format json`, a JSON object on stderr), including the labeled
  direct-HTTP commands `language-models list`, `status` and `enroll`.
- **Status messages go to stderr** (spinners, success lines, "No ...
  found"); stdout carries only data. An empty list prints `No results.` on
  stderr.
- **`connectivity connection update-secrets` and `update-export-settings`
  ask for confirmation**, because they overwrite the current values;
  `--yes`/`-y` skips it. When stdin is not a terminal they fail with exit
  code 2 unless `--yes` is given.
- **`connectivity import` commands take the connection RID first**, as the
  API nests imports under their connection:
  - `import file CONNECTION_RID DATASET_RID --name NAME --mode
    SNAPSHOT|APPEND|UPDATE [--subfolder PATH] [--branch NAME] [--filters
    JSON]` replaces `import file CONNECTION_RID SOURCE_PATH
    TARGET_DATASET_RID [--config JSON] [--execute]`. The source path is
    `--subfolder`.
  - `import table CONNECTION_RID DATASET_RID --name NAME --mode
    SNAPSHOT|APPEND --config JSON [--allow-schema-changes] [--branch NAME]`
    replaces `import table CONNECTION_RID SOURCE_TABLE TARGET_DATASET_RID
    [--config JSON] [--execute]`. `--config` is the API's table import
    config (its `type` and SQL `query`).
  - `get-file`/`get-table CONNECTION_RID IMPORT_RID` (was `IMPORT_RID`) and
    `list-file`/`list-table CONNECTION_RID` (was an optional
    `--connection/-c` filter).

  None of these commands could succeed before (see Fixed), so no working
  invocation breaks, and the old arguments aren't kept as aliases.
- **`audit list` fetches one page by default**; it read every page. Use
  `--all`, `--max-pages N` or `--page-token`. Paging stops at the first
  empty page and keeps its `nextPageToken`, because without `--end-date`
  the listing has no end (see Fixed).
- **`audit get` never writes to a terminal.** Pass `--output FILE` (`-` for
  stdout) or redirect stdout; otherwise it fails with exit code 2 before
  downloading. It used to print text content to the terminal and refuse
  only binary content.
- **New table and CSV columns:** `anthropic messages` and
  `messages-advanced` show the reply's text, tool calls, stop reason and
  token counts; `openai embeddings` shows one row per input (a vector
  preview in the table, the whole vector in CSV); connections show their
  configuration type, worker, egress policies and export settings.

### Added

- `connectivity import execute-file CONNECTION_RID FILE_IMPORT_RID` and
  `import execute-table CONNECTION_RID TABLE_IMPORT_RID` run an import and
  print the RID of the build that runs it (`FileImport.execute`,
  `TableImport.execute`; GA).
- `--page-size`, `--page-token`, `--max-pages` and `--all` on
  `connectivity import list-file`, `list-table` and `audit list`
  (`--page-size` already existed on `audit list`).
- `--format` on `connectivity connection update-secrets` and
  `update-export-settings` (JSON prints `null`) and on `audit get` (for how
  errors are reported).
- `PLTR_FORMAT` sets the default format of every command in these groups.
- `language-models anthropic messages-advanced --request` accepts
  `outputConfig`.
- `[beta]` labels in the help of `language-models anthropic messages`,
  `anthropic messages-advanced` and `openai embeddings`, which call beta
  Foundry endpoints, now always with `preview=true`.
- `language-models list` and `status` say on stderr which endpoint
  answered; `list` keeps an endpoint's `nextPageToken` in its JSON (it
  doesn't follow it).

### Changed

- `language-models anthropic messages`, `messages-advanced` and `openai
  embeddings` always send `preview=true`. They used to send the value of
  `--preview`, which defaulted to off, so the beta endpoints rejected them
  unless users remembered the flag (#184).
- `anthropic messages-advanced` reports unknown request fields (for example
  snake_case `max_tokens`) and a missing `messages` or `maxTokens` as usage
  errors that list the accepted fields; an invalid request (for example a
  thinking config without `budgetTokens`) is a usage error before anything
  is sent. The help's thinking example used `"budget"`; the field is
  `"budgetTokens"`.
- The model argument of `anthropic messages`, `messages-advanced` and
  `openai embeddings` is described as the model's API name: the SDK types it
  as `LanguageModelApiName`. The help used to call it a RID.
- `language-models list`, `status` and `enroll` try
  `/api/v2/languageModels...` first; they called `/v2/languageModels...` at
  the host root, outside Foundry's API. An endpoint whose answer isn't JSON
  is skipped like one that failed. Connection errors and missing
  credentials are reported at once instead of trying the next endpoint.
  When every endpoint fails, the error names each endpoint and its status,
  and carries the most telling failure's status code, Foundry error name
  and exit code.
- `connectivity connection upload-jdbc-drivers` reports each upload on
  stderr and prints the connection with its JDBC driver list.
- `connectivity connection update-secrets` rejects a secrets file that
  isn't a non-empty JSON object of string values (exit code 2) before
  calling the API.
- `language-models openai embeddings --encoding` accepts only `float` or
  `base64` (any case), checked by the option parser.
- `audit list` dates are checked by the option parser (`YYYY-MM-DD`).
- `audit get` streams the log file instead of reading it into memory, and
  deletes a partly written `--output` file when the download fails.

### Deprecated

- `--preview` on `language-models anthropic messages`, `anthropic
  messages-advanced` and `openai embeddings`: a hidden no-op that prints a
  deprecation warning. It will be removed in the next release.

### Removed

- `connectivity connection list`. The SDK has no endpoint that lists
  connections. The command scanned up to 1000 folders from the root folder
  (or from `$PLTR_CONNECTIONS_FALLBACK_START_FOLDER_RID`, also removed) for
  resources whose type contained "connection" or whose RID contained
  ".connection.". None of the SDK's resource types contains "connection"
  (Data Connection sources are `MAGRITTE_SOURCE` resources), so it is
  unlikely ever to have found one; it also passed `preview=` to the GA
  `Folder.children`. Find connections in a folder with
  `pltr folder list FOLDER_RID`.
- `connectivity import file`/`table --execute` (use `import
  execute-file`/`execute-table`), `import file --config` (use `--name`,
  `--mode`, `--filters`, `--subfolder`, `--branch`) and `import
  list-file`/`list-table --connection/-c` (now the `CONNECTION_RID`
  argument). None of them ever worked.
- The token-usage line of `anthropic messages`, `messages-advanced` and
  `openai embeddings` on stderr. It read the wrong keys and always printed 0;
  the table, CSV and JSON have the token counts.

### Fixed

- `connectivity import file`, `import table`, `get-file`, `get-table`,
  `list-file` and `list-table` always failed: they called
  `client.file_imports`/`client.table_imports`, which don't exist in the
  SDK. They now call `Connection.FileImport`/`Connection.TableImport` (GA)
  with the API's arguments.
- `connectivity connection get`, `create` and `upload-jdbc-drivers` printed
  `N/A` for fields a `Connection` doesn't have (#183).
- `language-models anthropic messages`, `messages-advanced` and `openai
  embeddings` failed without `--preview` (#184), and passed their arguments
  through a dict the SDK call check couldn't verify (#185).
- `audit list` passed its arguments through a dict (#185) and read every
  page. Without `--end-date` the API returns a `nextPageToken` on every page
  so that clients can poll for new log files, so that listing might never
  end; paging now stops at the first empty page.
- `audit get` printed log content through Rich, which interprets `[...]` as
  markup; content is now written unchanged.
- `language-models list`, `status` and `enroll` failures exited with 1 and
  printed the last endpoint's error text; see Changed.

### Docs to update

- `README.md` (lines 242-245, connectivity examples): `connection list` is
  gone; `import file`/`table` take `CONNECTION_RID DATASET_RID --name NAME
  --mode MODE ...`; `--execute` became `import execute-file`/`execute-table`.
- `docs/user-guide/commands.md`, connectivity section (from line 1118):
  remove `connection list`; new arguments of `import file`/`table`; the
  connection RID argument of `get-file`/`get-table`/`list-file`/`list-table`;
  the new `execute-file`/`execute-table`; `update-secrets` and
  `update-export-settings` need `--yes` when not interactive; `get-config`
  defaults to a table; JSON is the API's camelCase shape; exit codes. Its
  example RIDs (`ri.conn.main.connection.123`, `ri.import.main.file.12345`)
  don't look like Foundry RIDs: Data Connection sources look like
  `ri.magritte..source.<id>` (not verified live).
- `claude_skill/reference/connectivity-commands.md` and
  `claude_skill/workflows/data-pipeline.md` (lines 222-230): the same
  changes.
- `claude_skill/reference/language-models-commands.md` and
  `claude_skill/SKILL.md` (lines 141-145): the model argument of `messages`,
  `messages-advanced` and `embeddings` is the model's API name
  (`LanguageModelApiName`), not `ri.language-models.main.model.{uuid}`;
  `--preview` is a deprecated no-op; the default format is table; the
  extended-thinking example must use `"budgetTokens"` (more than 1024 and
  less than `maxTokens`), not `"budget"`; `messages-advanced` accepts
  `outputConfig`; the JSON is the API's response; list/status/enroll print
  the endpoint's objects.
- `audit list`/`audit get` aren't documented anywhere; worth a section in
  `docs/user-guide/commands.md` (paging; `get` needs `--output` or a
  redirect).
- `CHANGELOG.md`: fold this fragment into the release notes.

### Not verified live

- `language-models list`, `status` and `enroll` call endpoints that aren't
  in foundry-platform-sdk 1.111.0: `GET /api/v2/languageModels`,
  `GET /api/v2/languageModels/{id}`, `POST .../{id}/enroll`,
  `GET /api/v2/llm/models/{id}`, `POST /api/v2/llm/models/{id}/enroll` and
  the OpenAI-compatible proxy's `GET /api/v2/llm/proxy/openai/v1/models`.
  None was checked against a stack, and neither were their response shapes:
  pltr reads a `data` or `models` list, and the fields `rid`/`modelRid`/
  `id`/`apiName`/`name`, `displayName`, `status`/`enrollmentStatus` and
  `type`/`provider`/`modelType`/`family`/`owned_by`. The old first
  endpoints (`/v2/...` at the host root) were changed to `/api/v2/...`
  without a live check.
- The SDK types the model of `anthropic messages` and `openai embeddings` as
  `LanguageModelApiName` ("the name of the LanguageModel in the API");
  whether those endpoints also accept model RIDs wasn't checked.
- `openai embeddings --encoding base64`: the SDK's response model declares
  `data` as lists of floats. If the server answers with base64 strings, the
  SDK can't decode the response and pltr reports a usage error (exit 2).
- Data Connection source RIDs look like `ri.magritte..source.<id>` (the
  example in the help), and sources show up in `pltr folder list` as
  `MAGRITTE_SOURCE` resources; both come from Foundry's documentation and
  the SDK's resource types, not from a stack.
- `audit list --page-token` sends the start date along with the token, as
  the SDK's own iterator does; the API documents the start date as required
  only without a token.
- That `LogFile.list` without an end date returns a `nextPageToken` on every
  page (and an empty page once it has caught up) is read from the SDK's
  documentation of the endpoint, not observed.
- The format of audit log files (compressed or not) is unknown; `audit get`
  writes the content unchanged.
