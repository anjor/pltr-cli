### Breaking

- **`dataset`: `--format json` prints the SDK's own serialization.** Field
  names are the Foundry API's (camelCase), null fields are left out and the
  invented keys (`description`, `created_time`, `size_bytes`, `status:
  "deleted"`, `success`, ...) are gone. Lists print `{"data": [...],
  "nextPageToken": "..."}`. Per command:
  - `get`, `create`: the `Dataset`, `{"rid", "name", "parentFolderRid"}`.
  - `branches list/get/create`: `Branch` (`name`, `transactionRid`).
  - `files list/info/upload/get`: `File` (`path`, `transactionRid`,
    `sizeBytes` as a string, `updatedTime`); `files upload` of a directory
    and `files get --recursive` print `{"data": [...]}`.
  - `transactions start/commit/abort/status/list`, `branches transactions`:
    `Transaction` (`rid`, `transactionType`, `status`, `createdTime`,
    `closedTime`). Scripts that read `.transaction_rid` must read `.rid`.
  - `transactions build`: the build RID as a JSON string, or `null`.
  - `schema get`, `schema set`: the API response, `{"branchName",
    "endTransactionRid", "schema": {"fieldSchemaList": [...]}, "versionId"}`.
  - `schema apply`: the foundry-metadata endpoint's response body (or `null`).
  - `views *`: `View` (`viewName`, `datasetRid`, `parentFolderRid`, `branch`,
    `backingDatasets`, `primaryKey`).
  - `schedules list`: `{"data": ["<schedule RID>", ...]}` (the API returns
    RIDs only); `jobs list`: `{"data": [{"jobRid": ...}]}`.
  - `preview`: `{"data": [{"<column>": <value>, ...}]}` (was a bare list);
    BINARY values are base64.
  - `branches delete`, `files delete`: `null`.
- **`dataset` status messages go to stderr** and errors are structured, with
  the documented exit codes (2 usage, 3 authentication, 4 permission denied,
  5 not found, 6 validation, 7 other API or network error). Every error used
  to exit with 1. An invalid RID is now a usage error (exit 2).
- **`dataset` confirmations:** `schema set` and `schema apply` (they replace
  the branch's schema) and `views remove-datasets`/`replace-datasets` now ask
  for confirmation; `--yes`/`-y` skips it. `branches delete`, `files delete`
  and `transactions abort` no longer prompt when stdin is not a terminal:
  without `--yes` they fail with exit code 2.
- **`--branch` defaults to the dataset's default branch** (the API's default,
  `master` on most enrollments) instead of the literal `master`, on `files
  list/upload/get/delete/info`, `transactions start`, `schema set`, `views
  get` and `jobs list`. `schema apply` still defaults to `master` (its
  endpoint needs a branch name).
- **`dataset views create` takes new arguments:** `views create VIEW_NAME
  --parent-folder FOLDER_RID --backing-dataset DATASET_RID[@BRANCH] ...` (was
  `views create DATASET_RID VIEW_NAME [--description TEXT]`, which could never
  succeed). `--description` is a hidden option that fails with an
  explanation: views have no description in the API.
- **Paging:** `files list` uses the API's page size unless you pass
  `--page-size` (it used to send the `page_size` setting, 20 by default).
  `branches list`, `branches transactions`, `transactions list`, `schedules
  list` and `jobs list` fetch one page by default; use `--all`, `--max-pages`
  or `--page-token`.
- **`transactions list` lists every branch's transactions** unless you pass
  `--branch` (it defaulted to `master` and never worked).
- **`files get` prints the downloaded file's metadata** (the `File`) on stdout;
  it used to print only a status line.
- **Table and CSV columns changed for every `dataset` command.** They read
  real model fields; the old columns (created time, created by, content type,
  schedule names, job status, build duration, view description, ...) read
  fields the API doesn't return and were always empty.

### Added

- `dataset files upload` uploads a directory recursively in one transaction
  that pltr opens and commits, or aborts if an upload fails. New `--path`
  (where to put the file or directory in the dataset) and `--transaction-type`
  (APPEND, UPDATE or SNAPSHOT).
- `dataset files get --recursive/-r` downloads every file under a folder;
  `-` as the output path writes the content to stdout. Downloads are streamed
  and written atomically: a failed download leaves no partial file and keeps
  an existing one.
- `dataset files list --path-prefix`, and `--start-transaction-rid`/
  `--end-transaction-rid` on `files list`, `files get` and `files info`.
- `dataset files delete --transaction-rid` (an open DELETE transaction).
- `dataset preview --column` (repeatable) and `--branch`.
- `dataset schema get --transaction-rid` and `--version-id`.
- `dataset schema set --dataframe-reader` (AVRO, CSV, PARQUET, DATASOURCE).
  `--json` also accepts `@file.json`, the API's `{"fieldSchemaList": [...]}`
  and the JSON output of `schema get`; the older `{"fields": [...]}` form
  still works.
- `dataset branches create --transaction-rid`.
- `dataset views add-primary-key --latest-wins` and `--deletion-column`
  (duplicate keys resolved by latest row); `--branch` on every `views`
  command; `DATASET_RID@BRANCH` for backing datasets.
- `dataset jobs list --order-by started|finished` and `--ascending`;
  `dataset schedules list --branch`.
- `--page-size`, `--page-token`, `--max-pages` and `--all` on every paged
  `dataset` command; `--output` on most `dataset` commands; `PLTR_FORMAT`.
- `[beta]` labels: `dataset branches transactions`, `transactions list`,
  `transactions build` and `jobs list` call beta endpoints (with
  `preview=true`, no flag needed).

### Changed

- `dataset schema get` no longer warns that it needs API preview access:
  `Dataset.get_schema` is GA in foundry-platform-sdk 1.111.0.
- `dataset branches create --parent BRANCH` (default `master`) now starts the
  new branch at the parent's latest transaction (read with `Branch.get`).
- `dataset branches delete master` is refused as a usage error (exit 2).
- A leading `/` in a dataset file path is dropped (the API rejects such
  paths), so `files get DATASET "/data/x.csv" ...` works.
- `DatasetService` (for library use) returns SDK models: `create`,
  `get_dataset_schema`, `list_dataset_files`, `start_transaction`,
  `get_transaction`, `list_branches`, `list_transactions`,
  `list_branch_transactions`, `list_schedules`, `list_jobs`, `get_view`,
  `create_view`, `open_file_content`, `download_file`, `upload_file`, ...
  SDK exceptions propagate unchanged.

### Deprecated

- `DatasetService.create_dataset`, `get_schema`, `list_files`,
  `create_transaction` and `delete_dataset` remain only for `pltr cp`
  (`services/copy.py`), returning `to_dict()` results; they are removed when
  cp uses the model-returning methods.

### Removed

- `pltr dataset views list`: the SDK has no endpoint that lists a dataset's
  views.
- `dataset views create --description` (hidden, fails with an explanation).
- `DatasetService.list_files_paginated`, `get_branches`, `get_transactions`,
  `get_views`, `get_schedules`, `get_jobs`, `get_branch_transactions`,
  `get_transaction_status`, `preview_data` and the dict formatters.

### Fixed

- Commands that could never succeed (#182): `dataset branches list/create`
  (`datasets.list_branches`/`create_branch` don't exist), `branches
  transactions` and `transactions build` (beta without `preview`),
  `transactions list` (`Transaction.list` doesn't exist), `jobs list` (missing
  the required `order_by`, beta without `preview`), `views
  create/get/add-datasets/remove-datasets/replace-datasets/add-primary-key`
  (`Dataset.View` doesn't exist; wrong argument shapes), `preview`
  (`read_table(format="pandas")` isn't a valid format).
- `dataset files upload --transaction-rid` sent `branchName=master` too, which
  the API rejects (`InvalidParameterCombination`).
- `dataset schema set` validates the schema against the API's field types and
  reports problems as usage errors.
- `pltr cp`: copying a dataset's schema now works (`get_schema()["schema"]`
  used to be the whole response, which `put_schema` rejected, so the schema
  was always skipped), and a partially copied dataset is moved to the trash
  on failure (the cleanup called a method that doesn't exist).

### Docs to update

- `README.md`: the transactions examples (around lines 495-534) read
  `.transaction_rid` from `transactions start --format json`; use `.rid`.
  `transactions list` is `[beta]` and lists every branch without `--branch`.
- `docs/user-guide/commands.md`: remove `dataset views list`; `views create`
  now takes `VIEW_NAME --parent-folder --backing-dataset`; drop the note that
  `schema get` needs API preview access; `preview` JSON is `{"data": [...]}`;
  `files get` supports `-` and `--recursive`; `files upload` takes
  directories, `--path` and `--transaction-type`; `schema set`/`apply`,
  `views remove-datasets`/`replace-datasets` need `--yes` in scripts.
- `claude_skill/reference/dataset-commands.md`: same `views` changes; drop
  the `schema get` preview note; `transactions list` is `[beta]`.
- `docs/api/wrapper.md`: `DatasetService` returns SDK models (see Changed).

### Not verified live

- `dataset schema apply` calls internal endpoints whose shapes are assumed:
  the inference response carries `data.foundrySchema`, and the foundry-metadata
  response body is printed as-is.
- `branches create` from a parent branch whose latest transaction is OPEN
  (`Branch.create` may require a committed transaction).
- `views remove-datasets`/`replace-datasets` match backing datasets sent with
  an empty `stopPropagatingMarkingIds` list.
- `files upload --transaction-type` without `--branch` (the API documents
  `transactionType` for uploads that name a branch).
- `schema set --dataframe-reader CSV` making Foundry read uploaded CSV files.
- `pltr cp` cleanup trashing a dataset with `filesystem.Resource.delete`.
- Arrow decoding in `preview` for every Foundry type (DECIMAL, MAP, STRUCT,
  BINARY) and `read_table`'s row limit.
