### Breaking

- **`pltr cp`: a dataset copy fails when its schema can't be copied.** With
  `--schema` (the default) a failure to read the source's schema or to put it
  on the copy now moves the partial copy to the trash and exits with the
  error (it used to print a warning and exit 0, leaving a copy without a
  schema). A source without a schema (`SchemaNotFound`) is still copied
  without one. Pass `--no-schema` to copy only the files.

### Added

- Error type `invalid_response` (exit code 7): the API's response can't be
  read, because it doesn't match the SDK's model or isn't JSON.

### Changed

- `pltr cp` reads the source's schema from `--branch` (it read the default
  branch) and puts it on the committed copy of the files, on the same branch.
  The API doesn't report the source's dataframe reader, so the copy's schema
  gets `CSV` when every copied file is a `.csv` file, `AVRO` when every file
  is `.avro`, and the API's default (`PARQUET`) otherwise.
- `pltr cp` of a dataset with no files on `--branch` creates an empty copy
  with no schema (a schema needs a committed transaction), and says so.
- `pltr cp --help` explains the RID arguments and how datasets, schemas and
  failures are handled.
- `pltr <group> --help` shows the group's own help, with RID formats and
  examples, for `dataset`, `folder`, `project`, `resource`, `resource-role`,
  `space`, `ontology`, `orchestration`, `media-sets`, `connectivity` and
  `verify` (a one-line description used to replace it); `pltr --help` keeps
  the one-line summaries. `admin`, `sql` and `shell` show their modules'
  descriptions, and `pltr cp --help` its full description.
- `dataset preview` turns Arrow rows into output with the same shared code
  as `sql` (`pltr.contract.table_rows`): duplicate column names get a `_2`,
  `_3` suffix with a warning instead of the later column overwriting the
  earlier one. Values are unchanged (binary values are base64).
- `DatasetService.preview_rows()` is now `preview_table()` and returns the
  `pyarrow.Table`; `decode_arrow_rows()` is now `arrow_table()` (library
  API).
- `pltr` starts about three times faster: `pltr --help` took a median of
  1017 ms and now 370 ms (15 runs each, same machine), and shell completion
  speeds up the same way. Command and service modules import the SDK's model
  packages when a command runs, not at startup.
- `pltr.services.resource.RESOURCE_TYPES` is now the function
  `resource_types()` (library API), so the SDK isn't imported at startup.

### Deprecated

- The `page_size` setting (`settings.json` in the pltr configuration
  directory). No command reads it: list commands use the API's page size
  unless you pass `--page-size`. New settings files no longer get it, and a
  `page_size` in an existing file is accepted and ignored.

### Removed

- `DatasetService.create_dataset`, `get_schema`, `list_files`,
  `create_transaction` and `delete_dataset` (library API; deprecated
  compatibility wrappers kept only for `pltr cp`). Use `create`,
  `get_dataset_schema`, `list_dataset_files`, `start_transaction` and
  `ResourceService.delete_resource`.
- Legacy output helpers no command uses since every command moved to
  `pltr.contract` (library API): `pltr.utils.formatting` (`OutputFormatter`),
  `pltr.utils.progress` (`FileProgressTracker`, `SpinnerProgressTracker`,
  ...), `pltr.utils.pagination` (`PaginationConfig`, the pagination
  handlers), `BaseService._paginate_iterator`, `_paginate_response` and
  `_serialize_response`, and the unused completion helpers
  `complete_ontology_action`, `complete_file_path`,
  `setup_completion_environment`, `handle_completion` and
  `COMPLETION_FUNCTIONS`. Use `pltr.contract` (`emit`, `spinner`,
  `collect_pages`, `to_jsonable`).

### Fixed

- `pltr cp` never copied a dataset's schema. Besides passing the whole
  `GetDatasetSchemaResponse` where `put_schema` needs a `DatasetSchema` (see
  the dataset area's entry), it put the schema on the new dataset before any
  transaction existed; the API applies a schema to a committed transaction
  and documents `DatasetViewNotFound` for a dataset without one. It now
  copies the files, commits them and then puts the source's `DatasetSchema`
  with the branch and the committed transaction.
- `pltr cp`: listing the source's files is part of the file-copy step, so a
  listing failure also cleans up the new dataset with the context "Failed to
  copy the files of ...".
- A response that doesn't match the SDK's model (for example a field the
  installed SDK requires but a newer stack no longer sends) was reported as
  a usage error (exit 2, "Invalid argument"). It is now `invalid_response`
  (exit 7), and the message names the model and the mismatched fields and
  suggests upgrading pltr and the SDK. Invalid arguments (a bad RID, invalid
  JSON input) are still usage errors.
- A success response whose body isn't JSON (for example a proxy's sign-in
  page) was reported as "Invalid JSON input" (exit 2) by `dataset schema
  apply` and the `ontology object-type-create`/`link-type-create` fallback,
  and as an unexpected error (exit 1) by SDK calls. Both are now
  `invalid_response` (exit 7).
- A download that failed mid-stream deleted the file it was replacing
  (`media-sets download --overwrite`, `media-sets thumbnail-retrieve
  --overwrite`, `audit get --output`, `pltr api ... --output`). Binary output
  now goes to a temporary file next to the target, which replaces it only
  when the download is complete, so the old file is kept. Files written this
  way, including `dataset files get` downloads, get the usual permissions
  (dataset downloads were created readable by their owner only, 0600), a
  symlinked path keeps its symlink, and `/dev/null` or a FIFO is written
  directly.
- Unexpected failures inside the SDK (`SDKInternalError` that isn't an HTTP
  or OAuth failure) say "foundry-platform-sdk failed unexpectedly: ..." with
  a hint to report them (still `unexpected_error`, exit 1).

### Docs to update

- `CHANGELOG.md`: merge `b1-dataset.md`'s "`pltr cp`: copying a dataset's
  schema now works" with the cp schema entry above (the fix needs both), and
  drop `b1-dataset.md`'s Deprecated entry for the `DatasetService` compat
  methods (they are removed now).
- `docs/pagination.md`: the "Related Settings" section (around line 431)
  lists `page_size` ("Default items per page (default: 20)") as a setting;
  it is deprecated and unused (use `--page-size`). The `pltr config show`
  command it mentions doesn't exist.
- `docs/api/wrapper.md` describes `OutputFormatter`, `utils/progress.py` or
  `utils/pagination.py`, which are removed (see Removed).
- Exit-code tables: add `invalid_response` to exit code 7 ("the API's
  response doesn't match the SDK's model or isn't JSON: upgrade pltr; a
  retry won't help") in `README.md` (line ~189), `docs/api-commands.md`
  (line ~213) and `claude_skill/SKILL.md` (line ~100, "What to do": upgrade
  pltr rather than retry).
- `README.md` and `docs/user-guide/commands.md` (cp sections): a dataset
  copy copies the schema after the files and fails (trashing the copy) when
  the schema can't be copied; `--no-schema` copies only the files. (The
  generated `claude_skill/reference/` is regenerated on this branch.)

### Not verified live

- `pltr cp`'s dataset sequence (create, list files, start a SNAPSHOT
  transaction, download, upload into the transaction, commit, get the source
  schema on `--branch`, put it with `branchName` and the committed
  `endTransactionRid`) was only run against stubbed HTTP.
- That `getSchema` answers `SchemaNotFound` (not `DatasetViewNotFound`) for a
  source that has files but no schema.
- That `putSchema` with `dataframeReader: CSV` makes Foundry read copied CSV
  files (it depends on the copied files having a header row the reader
  expects), and that the PARQUET default fits datasets built by transforms.
- That decode failures look the same on a real stack: the rule reads where
  the pydantic error was raised (SDK code after `validate_call` means the
  response) and was checked against foundry-platform-sdk 1.111.0 and
  pydantic 2.11 only.
- `pltr cp --branch X` for a branch other than the new dataset's default
  branch: `Dataset.create` makes only the default branch, so starting the
  transaction on `X` may fail with `BranchNotFound` (behaviour unchanged).
