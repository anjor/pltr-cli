# CSV Upload Examples

Examples for uploading CSV files to Foundry datasets with pltr-cli.

## Prerequisites

- pltr-cli installed and configured
- Authentication set up (see [Quick Start Guide](../user-guide/quick-start.md)); in CI,
  set `FOUNDRY_HOST` and `FOUNDRY_TOKEN` instead of configuring a profile
- Write permissions on the dataset, or on the folder you create datasets in

Datasets are addressed by RID (`ri.foundry.main.dataset.<id>`), folders and projects
by folder RID (`ri.compass.main.folder.<id>`).

With `--format json`, pltr prints only the API's JSON on stdout (status messages go to
stderr), so `jq` can read the output directly. Commands that replace or delete data
(`schema set`, `schema apply`, `transactions abort`, `files delete`) ask for
confirmation; scripts must pass `--yes`, because pltr never prompts when stdin isn't a
terminal.

## Simple CSV Upload to a New Dataset

```bash
#!/bin/bash
# upload_csv_simple.sh - upload one CSV file to a new dataset
set -euo pipefail

CSV_FILE="data.csv"
DATASET_NAME="sales_data_$(date +%Y%m%d)"
PARENT_FOLDER="ri.compass.main.folder.your-folder-rid"  # a project or folder

# Create the dataset
DATASET_RID=$(pltr dataset create "$DATASET_NAME" \
  --parent-folder "$PARENT_FOLDER" --format json | jq -r '.rid')
echo "Created dataset: $DATASET_RID"

# Upload the file (the API opens and commits a transaction for it)
pltr dataset files upload "$CSV_FILE" "$DATASET_RID"

# Infer the schema from the uploaded file and apply it
pltr dataset schema apply "$DATASET_RID" --yes
```

### Verify the Upload

```bash
pltr dataset get "$DATASET_RID"
pltr dataset files list "$DATASET_RID"
pltr dataset schema get "$DATASET_RID"

# Read the first rows, as a table, JSON or CSV
pltr dataset preview "$DATASET_RID" --limit 20
pltr dataset preview "$DATASET_RID" --limit 1000 --format csv --output sample.csv

# Query it with SQL
pltr sql execute "SELECT COUNT(*) AS row_count FROM \`$DATASET_RID\`"
```

## Upload Several CSV Files

Upload a whole directory: pltr opens one transaction, uploads every file (keeping
their relative paths), and commits it. If any upload fails, pltr aborts the
transaction, so the dataset never shows a partial upload.

```bash
DATASET_RID="ri.foundry.main.dataset.your-dataset-rid"

pltr dataset files upload ./csv_files "$DATASET_RID" --path raw
```

If you need to run other steps inside the transaction, manage it yourself:

```bash
#!/bin/bash
# batch_csv_upload.sh - upload several files in one transaction you control
set -uo pipefail

DATASET_RID="ri.foundry.main.dataset.your-dataset-rid"

TRANSACTION_RID=$(pltr dataset transactions start "$DATASET_RID" --type APPEND \
  --format json | jq -r '.rid') || exit 1

for csv_file in ./csv_files/*.csv; do
  # --transaction-rid and --branch can't be combined (the API rejects it)
  if ! pltr dataset files upload "$csv_file" "$DATASET_RID" \
      --transaction-rid "$TRANSACTION_RID"; then
    echo "Failed to upload $csv_file; aborting"
    pltr dataset transactions abort "$DATASET_RID" "$TRANSACTION_RID" --yes
    exit 1
  fi
done

pltr dataset transactions commit "$DATASET_RID" "$TRANSACTION_RID"
```

## Replace a Dataset's Contents

A SNAPSHOT transaction replaces all of the dataset's files with the ones in the
transaction (older versions stay in the dataset's history):

```bash
pltr dataset files upload updated_data.csv "$DATASET_RID" --transaction-type SNAPSHOT

# or a whole directory
pltr dataset files upload ./export "$DATASET_RID" --transaction-type SNAPSHOT
```

## Schema Management for CSV Datasets

### Infer the Schema from the Uploaded Files (recommended)

```bash
pltr dataset schema apply "$DATASET_RID" --yes            # branch master
pltr dataset schema apply "$DATASET_RID" --branch dev --yes
```

`schema apply` asks Foundry to infer the schema, including how to parse the CSV
files, from the files on the branch, and applies it. Foundry's public API has no
schema inference, so this command calls Foundry's internal schema-inference and
foundry-metadata endpoints directly (a documented exception to pltr's SDK-only rule).

### Infer the Schema from a Local CSV File

```bash
pltr dataset schema set "$DATASET_RID" --from-csv sales_data.csv \
  --dataframe-reader CSV --yes
pltr dataset schema get "$DATASET_RID" --format json
```

pltr reads the header and the first 100 rows and picks a type for each column
(INTEGER, DOUBLE, BOOLEAN, DATE, TIMESTAMP, else STRING); a column with empty values
is nullable. Spaces and hyphens in column names become underscores. The API reads
files as Parquet unless you pass `--dataframe-reader`, so pass `CSV` for CSV files.

### Define the Schema Yourself

Give the schema in the API's format, inline, from a file (`@schema.json` or
`--json-file`), or as the JSON output of `pltr dataset schema get`:

```bash
SCHEMA_JSON='{
  "fieldSchemaList": [
    {"name": "id", "type": "INTEGER", "nullable": false},
    {"name": "name", "type": "STRING", "nullable": false},
    {"name": "email", "type": "STRING", "nullable": true},
    {"name": "amount", "type": "DECIMAL", "precision": 12, "scale": 2, "nullable": false},
    {"name": "created_date", "type": "DATE", "nullable": false},
    {"name": "is_active", "type": "BOOLEAN", "nullable": false}
  ]
}'

pltr dataset schema set "$DATASET_RID" --json "$SCHEMA_JSON" --dataframe-reader CSV --yes

# Copy the schema of one dataset to another
pltr dataset schema get "$SOURCE_RID" --format json > schema.json
pltr dataset schema set "$TARGET_RID" --json-file schema.json --yes
```

Field types: ARRAY, BINARY, BOOLEAN, BYTE, DATE, DECIMAL, DOUBLE, FLOAT, INTEGER,
LONG, MAP, SHORT, STRING, STRUCT, TIMESTAMP. The older shorthand
`{"fields": [{"name": ..., "type": ..., "nullable": ...}]}` is still accepted
(`nullable` defaults to true).

## Validate a CSV Before Uploading

```bash
#!/bin/bash
# csv_with_schema.sh - check the header, then upload
set -euo pipefail

CSV_FILE="structured_data.csv"
DATASET_RID="ri.foundry.main.dataset.your-dataset-rid"
EXPECTED_COLUMNS="id,name,email,created_date,amount"

headers=$(head -n 1 "$CSV_FILE" | tr '[:upper:]' '[:lower:]' | tr -d '\r')
if [ "$headers" != "$EXPECTED_COLUMNS" ]; then
  echo "Header mismatch: expected $EXPECTED_COLUMNS, found $headers"
  exit 1
fi

pltr dataset files upload "$CSV_FILE" "$DATASET_RID"
```

## Large Files

- The upload API takes each file in a single request, so pltr reads the file into
  memory. For very large CSV files, split them and upload the directory in one
  transaction:

  ```bash
  mkdir parts && split -l 1000000 large.csv parts/part_
  pltr dataset files upload ./parts "$DATASET_RID" --path large --transaction-type SNAPSHOT
  ```

  Each part needs its own header row if the schema expects one.
- Downloads are streamed to disk, so they don't need to fit in memory:

  ```bash
  pltr dataset files get "$DATASET_RID" large/part_aa ./part_aa.csv
  pltr dataset files get "$DATASET_RID" large ./large --recursive
  ```

## Incremental Updates

Append each new file under a timestamped path, one transaction per file:

```bash
#!/bin/bash
# incremental_update.sh - append new CSV files to a dataset
set -uo pipefail

DATASET_RID="ri.foundry.main.dataset.your-dataset-rid"
mkdir -p ./processed

for csv_file in ./daily_updates/*.csv; do
  [ -f "$csv_file" ] || continue
  target="updates/$(date +%Y%m%d_%H%M%S)_$(basename "$csv_file")"

  if pltr dataset files upload "$csv_file" "$DATASET_RID" \
      --path "$target" --transaction-type APPEND; then
    mv "$csv_file" ./processed/
  else
    echo "Failed to upload $csv_file"
  fi
done
```

## Error Handling and Retries

pltr exits with documented codes: 2 usage error, 3 authentication, 4 permission
denied, 5 not found, 6 invalid request, 7 other API or network errors (conflicts,
rate limits, server errors, timeouts). Only 7 is worth retrying:

```bash
#!/bin/bash
# robust_csv_upload.sh - retry transient failures only
CSV_FILE="important_data.csv"
DATASET_RID="ri.foundry.main.dataset.your-dataset-rid"

for attempt in 1 2 3; do
  pltr dataset files upload "$CSV_FILE" "$DATASET_RID" --format json \
    2> upload-errors.jsonl
  status=$?
  [ $status -eq 0 ] && { echo "Uploaded on attempt $attempt"; exit 0; }
  [ $status -ne 7 ] && break    # not transient: don't retry
  sleep 10
done

# The last stderr line is a JSON error with errorName, statusCode and parameters
tail -n 1 upload-errors.jsonl | jq .
exit 1
```

## Python

pltr's services wrap `foundry-platform-sdk` and return its models. For programs, the
SDK itself (`foundry_sdk.FoundryClient`) is the stable interface; pltr's services are
convenient when you want pltr's profiles and environment-variable authentication:

```python
#!/usr/bin/env python3
"""csv_upload.py - upload a CSV file to a new dataset in one transaction."""

import sys
from pathlib import Path

from pltr.services.dataset import DatasetService


def upload_csv(csv_path: Path, dataset_name: str, parent_folder_rid: str) -> str:
    service = DatasetService()  # the active profile, or FOUNDRY_* variables
    dataset = service.create(dataset_name, parent_folder_rid=parent_folder_rid)
    transaction = service.start_transaction(dataset.rid, transaction_type="SNAPSHOT")
    try:
        service.upload_file(
            dataset.rid, csv_path, csv_path.name, transaction_rid=transaction.rid
        )
        service.commit_transaction(dataset.rid, transaction.rid)
    except Exception:
        service.abort_transaction(dataset.rid, transaction.rid)
        raise
    return dataset.rid


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("Usage: csv_upload.py <csv_file> <dataset_name> <parent_folder_rid>")
    print(upload_csv(Path(sys.argv[1]), sys.argv[2], sys.argv[3]))
```

## Tips

- Prefer `pltr dataset files upload <directory>`: one atomic change, aborted on failure.
- Use `--path` to organize files in folders inside the dataset, and timestamps to
  avoid name collisions.
- Use `schema apply` after uploading CSV files; use `schema set` when you need exact
  types.
- Validate CSV headers before uploading, and test scripts on a small dataset first.

## Troubleshooting

1. **Authentication errors (exit code 3)**: run `pltr verify`; configure a profile with
   `pltr configure configure`, or set `FOUNDRY_HOST` and `FOUNDRY_TOKEN`.
2. **Permission denied (exit code 4)**: you need write access to the dataset or folder.
3. **A transaction is already open (`OpenTransactionAlreadyExists`, exit code 7)**:
   list transactions with `pltr dataset transactions list <dataset_rid>` (a beta
   endpoint), then commit or abort the open one:
   `pltr dataset transactions abort <dataset_rid> <transaction_rid> --yes`.
4. **`InvalidParameterCombination`**: don't pass `--branch` together with
   `--transaction-rid`; pltr rejects that combination before calling the API.
5. **Schema issues**:
   - Check the current schema: `pltr dataset schema get <dataset_rid>`.
   - Re-infer it from the uploaded files: `pltr dataset schema apply <dataset_rid> --yes`.
   - If reads fail after `schema set`, check `--dataframe-reader` (CSV for CSV files).

## Related Documentation

- [Dataset Commands Reference](../user-guide/commands.md#dataset-commands)
- [Dataset Transactions](../features/dataset-transactions.md)
- [Authentication Setup](../user-guide/authentication.md)
- [Examples Gallery](gallery.md)
