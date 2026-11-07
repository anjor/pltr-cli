### Breaking

- **`pltr cp`: a dataset copy fails when its schema can't be copied.** With
  `--schema` (the default) a failure to read the source's schema or to put it
  on the copy now moves the partial copy to the trash and exits with the
  error (it used to print a warning and exit 0, leaving a copy without a
  schema). A source without a schema (`SchemaNotFound`) is still copied
  without one. Pass `--no-schema` to copy only the files.

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

### Removed

- `DatasetService.create_dataset`, `get_schema`, `list_files`,
  `create_transaction` and `delete_dataset` (library API; deprecated
  compatibility wrappers kept only for `pltr cp`). Use `create`,
  `get_dataset_schema`, `list_dataset_files`, `start_transaction` and
  `ResourceService.delete_resource`.

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

### Docs to update

- `CHANGELOG.md`: merge `b1-dataset.md`'s "`pltr cp`: copying a dataset's
  schema now works" with the cp schema entry above (the fix needs both), and
  drop `b1-dataset.md`'s Deprecated entry for the `DatasetService` compat
  methods (they are removed now).
- `README.md`, `docs/user-guide/commands.md` and
  `claude_skill/reference/dataset-commands.md` (cp sections): a dataset copy
  copies the schema after the files and fails (trashing the copy) when the
  schema can't be copied; `--no-schema` copies only the files.

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
- `pltr cp --branch X` for a branch other than the new dataset's default
  branch: `Dataset.create` makes only the default branch, so starting the
  transaction on `X` may fail with `BranchNotFound` (behaviour unchanged).
