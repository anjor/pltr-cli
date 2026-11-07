### Breaking

- **`sql`, `streams` and `media-sets`: `--format json` prints the SDK's own
  serialization**: Foundry API field names (camelCase), no null fields, no
  invented fields.
  - `sql execute`, `sql results`, `sql wait` and `sql export` (to a `.json`
    file) print `{"data": [...]}` with one object per result row, keyed by
    column name. Binary values are base64 strings, NaN/Infinity are `null`,
    and duplicate column names (`SELECT a.id, b.id ...`) get a `_2`, `_3`
    suffix with a warning instead of losing values. Before, `execute` and
    `wait` printed a bare JSON array preceded by `Query ID:`/`Status:` text on
    stdout, which wasn't valid JSON.
  - `sql submit`, `sql status` and `sql cancel` print the API's query status:
    `{"type": "running", "queryId": "..."}`, `{"type": "succeeded",
    "queryId": "..."}`, `{"type": "failed", "errorMessage": "..."}` or
    `{"type": "canceled"}`. They used to print text lines on stdout and had no
    `--format`.
  - `streams dataset create` prints the API's `Dataset` (`rid`, `name`,
    `parentFolderRid`); `streams stream create`/`get`/`reset` print the
    `Stream` (`branchName`, `schema`, `viewRid`, `partitionsCount`,
    `streamType`, `compressed`). `publish` and `publish-batch` print `null`.
  - `media-sets get` prints the API's `GetMediaItemInfoResponse` (`viewRid`,
    `path`, `logicalTimestamp`, `attribution`, `mimeType`,
    `originallyUploadedFileMimeType`, `sizeBytesLong`, ...); `get-by-path`
    prints `{"mediaItemRid": "..."}`; `reference` and `upload-temp` print the
    `MediaReference` (`mimeType`, `reference.mediaSetViewItem`);
    `thumbnail-calculate` prints `{"type": "pending"|"successful"|"failed"}`;
    `create` prints the transaction ID as a JSON string; `upload` prints
    `{"mediaItemRid": "...", "mediaSetViewRid": "..."}`; `commit`, `abort`
    and `clear` print `null`.
- **Status messages moved to stderr** in these areas, including the query ID
  that `sql execute` and `sql export` print. stdout carries data only.
- **New exit codes** in these areas (they used to exit 1 on every error):
  2 usage error, 3 authentication, 4 permission denied, 5 not found,
  6 validation, 7 other API or network error. In particular:
  - a query that fails or is canceled exits 7 (`api_error`) from
    `sql execute`, `submit`, `wait` and `export`; reaching `--timeout` exits 7
    (`timeout`) and leaves the query running;
  - `sql results` for a query that is still running exits 6 (the API's
    `QueryRunning`), and for a failed query 7 (`QueryFailed`);
  - `media-sets download`/`thumbnail-retrieve` to an existing file without
    `--overwrite` exits 2; an empty thumbnail exits 7.
- **`sql wait` always prints the query's rows** once it succeeds, in every
  format, like `sql results`. It used to print the status as text and fetch
  the rows only with `--output` or a non-table `--format`.
- **`sql results` no longer checks the status first.** It asks for the
  results directly: while the query runs, the API waits up to a minute for
  it and then fails with `QueryRunning`. Use `sql wait` to wait longer.
- **`sql submit` fails when the query fails or is canceled right away**
  (exit 7). It used to report "Query submitted successfully".
- **`sql cancel` asks for confirmation**; `--yes`/`-y` skips it. Without
  `--yes` it fails with exit code 2 when stdin is not a terminal.
- **`streams stream reset` and `media-sets abort` use the shared
  confirmation:** answering "no" exits 1 (`stream reset` used to exit 0),
  and without `--yes` they fail with exit code 2 when stdin is not a
  terminal instead of prompting.
- **`media-sets commit` no longer asks for confirmation** (like
  `dataset transactions commit`): committing makes uploads available and
  deletes nothing.
- **Table and CSV columns changed** to fields that exist (#183):
  - `media-sets get` showed `unknown`, `0` or nothing for `filename`, `size`,
    `content_type`, `created_time` and `updated_time`. It now shows the item
    RID you passed, path, MIME type, size, originally uploaded MIME type,
    view RID, logical timestamp, and who uploaded it when.
  - `media-sets reference` and `upload-temp` showed `unknown` for
    `reference_id`, `url` and `expires_at`. They now show the MIME type, the
    media set, media set view and media item RIDs, and the token.
  - `media-sets thumbnail-calculate` showed status `unknown`; it now shows
    the calculation status.
  - `sql status`/`submit`/`cancel` show Query ID, Status and (when failed)
    Error; `streams stream ...` show branch, view RID, type, partitions,
    compression, fields and key fields.
  - `streams dataset create` no longer prints a "Stream RID" line: the API's
    response has no stream RID, so it was always empty.
- **`streams` schemas:** the `--schema` format the help documented,
  `{"fieldSchemaList": [{"name": ..., "type": ...}]}`, was never accepted by
  the SDK, so those examples always failed. The help now documents the real
  Foundry stream schema, `{"fields": [{"name": "id", "schema": {"nullable":
  false, "dataType": {"type": "long"}}}], "keyFieldNames": ["id"]}`, and the
  old shape is rejected with a usage error (exit 2) before any request.
- **`streams ... --type`** only accepts `LOW_LATENCY` or `HIGH_THROUGHPUT`
  (case-insensitive); other values used to reach the API.
- **`media-sets download` and `thumbnail-retrieve` stream the content**
  instead of loading it into memory first, writing it in place. If a
  download fails mid-stream, the partly written file is deleted; with
  `--overwrite` the file it replaced is then gone too. API errors (403, 404,
  ...) happen before anything is written and leave an existing file alone.

### Added

- **`media-sets clear MEDIA_SET_RID MEDIA_ITEM_PATH`** [beta] (#170):
  soft-delete the media item at a path (it and all older items at that path
  become unretrievable). Options `--branch`, `--transaction-id` (required
  for transactional media sets) and `--yes`/`-y`; it asks for confirmation.
- `media-sets download` and `thumbnail-retrieve` accept `-` as OUTPUT_PATH to
  write the content to stdout (and nothing else).
- `media-sets upload`: TRANSACTION_ID is optional (needed only for
  transactional media sets), and `--branch` picks the branch.
- `streams stream reset`: `--schema`, `--partitions`, `--type` and
  `--compressed/--no-compressed` apply new stream settings (the SDK's reset
  options); settings you don't pass keep their current values.
- `--no-compressed` on `streams dataset create` and `streams stream create`.
- `streams` JSON inputs (`--schema`, `--record`, `--records`) accept `@-` to
  read stdin.
- Shared options where they were missing:
  - `--format`/`-f` and `--output`/`-o` on `sql submit`, `status` and
    `cancel`; `-f`, `-o` and `-p` on `sql execute`, `results` and `wait`;
    `-f` and `-p` on `sql export`.
  - `--format`/`-f` on `streams stream publish` and `publish-batch`; `-f` and
    `--output`/`-o` on `streams stream create`, `get` and `reset`;
    `--output`/`-o` on `streams dataset create` (its `-f` is `--folder`).
  - `--format`/`-f` on `media-sets create`, `commit`, `abort`, `upload`,
    `download`, `thumbnail-retrieve` and `clear`; `--output`/`-o` on
    `media-sets create` and `upload`.
- `PLTR_FORMAT` sets the default `--format` of these commands. For
  `sql export`, the file extension wins over `PLTR_FORMAT`; only `--format`
  on the command line overrides it.

### Changed

- Beta endpoints are always called with `preview=True` and their commands
  are labeled `[beta]`, so they work without `--preview` (#184):
  `streams dataset create`, `streams stream create`, `streams stream reset`,
  and `media-sets get-by-path`, `create`, `commit`, `abort`, `upload`,
  `reference`, `thumbnail-calculate`, `thumbnail-retrieve` (and the new
  `clear`). They used to fail unless `--preview` was given.
- GA endpoints are called without `preview`, so they no longer print a
  `UserWarning`: every `sql` command, and `streams stream get`, `publish`
  and `publish-batch`.
- Help texts give the RID formats: media sets are
  `ri.mio.main.media-set.<uuid>` and media items
  `ri.mio.main.media-item.<uuid>` (the help used to say
  `ri.mediasets.main.media-set...`).

### Deprecated

- `--preview` on every `streams` and `media-sets` command, and
  `--preview/--no-preview` on every `sql` command: hidden, no effect, a
  warning on stderr. They will be removed in a future release.
- `streams stream reset --confirm`: a hidden alias of `--yes` that warns.
- `media-sets commit --yes`/`-y`: hidden, no effect (commit doesn't ask any
  more), a warning on stderr.

### Fixed

- `media-sets get-by-path` could never succeed: it read a `rid` attribute
  that `GetMediaItemRidByPathResponse` doesn't have (the field is
  `mediaItemRid`).
- The `media-sets` formatters that read nonexistent fields (#183), see
  Breaking.
- `streams` beta commands failed without `--preview`, and GA ones warned on
  every call (#184).
- `sql` JSON output was not valid JSON (status text on stdout).

### Docs to update

- `README.md` (media sets section): RIDs `ri.mediasets.main.media-set.abc` /
  `ri.mediasets.main.media-item.123` should be `ri.mio.main.media-set.<uuid>` /
  `ri.mio.main.media-item.<uuid>`; `media-sets commit ... --yes` no longer
  needs `--yes`; "Preview mode (`--preview`)" bullets for media sets no longer
  apply; mention `media-sets clear` and `-` for downloads.
- `docs/user-guide/commands.md`:
  - SQL: drop "All SQL commands default to `--preview` mode, which is
    required by the Foundry API" and the `--preview/--no-preview` option
    rows; `sql cancel` asks for confirmation (`--yes`); `sql wait` always
    prints rows; JSON output is `{"data": [...]}`.
  - Media sets: same RID fix as the README (also the "Media Sets/Media Items"
    RID list); drop the `--preview` option rows and `commit ... --yes`;
    `upload`'s TRANSACTION_ID is optional; add `media-sets clear`.
- `docs/user-guide/workflows.md`, `docs/user-guide/troubleshooting.md`,
  `claude_skill/reference/sql-commands.md` and
  `claude_skill/workflows/data-analysis.md`: `QUERY_ID=$(pltr sql submit "...")`
  never captured just the ID; use
  `QUERY_ID=$(pltr sql submit "..." --format json | jq -r .queryId)`.
  `troubleshooting.md` also suggests `--no-preview`, which no longer does
  anything.
- `claude_skill/reference/streams-commands.md`: every `--schema` example uses
  the `fieldSchemaList` format, which never worked; use the `fields` format
  above. `stream reset --confirm` becomes `--yes`.
- `claude_skill/reference/mediasets-commands.md`: RID formats, `--preview`
  flags, `commit ... --yes`, JSON shapes, and the new `clear` command.
- `cli.py` registers `media-sets` with `help="Manage media sets and media
  content"`, which hides the group docstring (RID formats and examples) from
  `pltr media-sets --help`; the per-command help carries the RID formats.

### Not verified live

- `sql`: the Arrow IPC results decoding (verified live in #171) and the CSV
  fallback for queries executed with `serializationFormat` CSV elsewhere;
  that `getResults` long-polls about a minute and then fails with
  `QueryRunning` for a running query (from the SDK docs); that the cancel
  endpoint is a no-op for a finished query.
- `streams`: that the live API accepts the documented `StreamSchema`
  example; the high-scale publish endpoints are called at
  `<host>/api/v2/highScale/...` (the SDK's static-hostname mapping).
- `media-sets`: that `get-by-path` answers 200 with no `mediaItemRid` when
  no item exists at the path (pltr then warns and exits 0; a 404 would exit
  5); that `create` returns the transaction ID as a bare JSON string; that a
  thumbnail that isn't calculated yet comes back as an empty 200 response;
  that `calculate` can be called again to check the status; that `upload`
  works without a transaction on non-transactional media sets; `clear`
  semantics (soft delete at a path).
