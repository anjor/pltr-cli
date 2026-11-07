# Dataset Transaction Management

## Overview

Foundry datasets change through transactions: you open a transaction on a
branch, add or delete files in it, then commit it (the changes become visible
together) or abort it (nothing changes). pltr exposes the whole lifecycle,
and also manages a transaction for you when you upload a directory.

Datasets and transactions are addressed by RID: datasets look like
`ri.foundry.main.dataset.<id>`, transactions like
`ri.foundry.main.transaction.<id>`. Branches are addressed by name.

## Key Features

- **Atomic changes**: the files of a transaction become visible together, at commit
- **Rollback**: abort a transaction to discard everything in it
- **Transaction types**: APPEND, UPDATE, SNAPSHOT and DELETE
- **Managed uploads**: `pltr dataset files upload <directory>` uploads every file in one
  transaction and aborts it if any upload fails
- **Scriptable**: `--format json` prints only the API's JSON on stdout, and failures
  exit with documented codes (see [Error Handling](#error-handling))

## Uploading Without Managing Transactions

For most uploads you don't need to open a transaction yourself:

```bash
# One file: the API opens and commits a transaction for the upload
pltr dataset files upload data.csv ri.foundry.main.dataset.abc123

# A directory: pltr opens one transaction, uploads every file, commits it,
# or aborts it if any upload fails
pltr dataset files upload ./exports ri.foundry.main.dataset.abc123 --path exports

# Replace the dataset's files with the directory's contents (asks first;
# --yes skips the question)
pltr dataset files upload ./exports ri.foundry.main.dataset.abc123 \
  --transaction-type SNAPSHOT --yes
```

`--branch <name>` uploads to another branch (default: the dataset's default
branch, `master` on most enrollments). `--transaction-type` sets the type of
the transaction (default: UPDATE); with it, pltr opens the transaction for a
single file too, uploads into it and commits it. A SNAPSHOT upload replaces
every file on the branch, so it asks for confirmation, and without a terminal
it fails unless you pass `--yes`.

## Transaction Lifecycle

Open a transaction yourself when you want to combine several commands (uploads,
deletes, a validation step) into one change.

### 1. Starting a Transaction

```bash
pltr dataset transactions start <dataset-rid> [options]
```

**Options:**
- `--branch <name>`: Branch to open the transaction on (default: the dataset's default
  branch, `master` on most enrollments)
- `--type <type>`: APPEND (default), UPDATE, SNAPSHOT or DELETE
- `--profile <name>`: Authentication profile to use
- `--format <format>`: Output format (table, json, csv)

A branch can have only one open transaction at a time.

**Example:**
```bash
pltr dataset transactions start ri.foundry.main.dataset.abc123 --type APPEND
```

The JSON output is the API's `Transaction`:

```json
{
  "rid": "ri.foundry.main.transaction.xyz",
  "transactionType": "APPEND",
  "status": "OPEN",
  "createdTime": "2024-03-04T05:06:07+00:00"
}
```

### 2. Performing Operations

Pass `--transaction-rid` to upload into (or delete from) an open transaction. The
transaction stays open until you commit or abort it. Don't combine
`--transaction-rid` with `--branch`: the API rejects the combination.

```bash
# Upload files
pltr dataset files upload data.csv ri.foundry.main.dataset.abc123 \
  --transaction-rid ri.foundry.main.transaction.xyz

# Upload a whole directory into the same transaction
pltr dataset files upload ./more ri.foundry.main.dataset.abc123 \
  --transaction-rid ri.foundry.main.transaction.xyz

# Delete a file (the transaction must be a DELETE transaction)
pltr dataset files delete ri.foundry.main.dataset.abc123 old.csv \
  --transaction-rid ri.foundry.main.transaction.del --yes
```

To see which files a transaction changed, list the files of that transaction:

```bash
pltr dataset files list ri.foundry.main.dataset.abc123 \
  --start-transaction-rid ri.foundry.main.transaction.xyz \
  --end-transaction-rid ri.foundry.main.transaction.xyz
```

### 3. Checking Transaction Status

```bash
pltr dataset transactions status <dataset-rid> <transaction-rid>
```

Shows the transaction's type, status (OPEN, COMMITTED or ABORTED) and its created
and closed times.

### 4. Committing Changes

```bash
pltr dataset transactions commit <dataset-rid> <transaction-rid>
```

### 5. Aborting a Transaction

```bash
pltr dataset transactions abort <dataset-rid> <transaction-rid> [--yes]
```

Aborting discards the transaction's changes, so pltr asks for confirmation.
`--yes` (or `-y`) skips the prompt; scripts and agents must pass it, because pltr
never prompts when stdin is not a terminal (the command fails with exit code 2
instead).

## Transaction Types

| Type | Effect when committed |
|---|---|
| APPEND | Adds new files; existing files are unchanged |
| UPDATE | Adds files and replaces files with the same path |
| SNAPSHOT | Replaces all of the dataset's files with the transaction's files |
| DELETE | Removes the files deleted in the transaction |

## Listing Transactions

```bash
pltr dataset transactions list <dataset-rid> [options]
```

Lists transactions newest first. This calls a beta Foundry endpoint, so the
command is labeled `[beta]`.

**Options:**
- `--branch <name>`: Only this branch's transactions (default: every branch)
- `--page-size`, `--page-token`, `--max-pages`, `--all`: Paging (one page by default)
- `--format <format>`, `--output <file>`

`pltr dataset branches transactions <dataset-rid> <branch>` lists one branch's
transactions too, and `pltr dataset transactions build <dataset-rid>
<transaction-rid>` shows the RID of the build that produced a transaction, if any
(both `[beta]`).

## Practical Examples

### Example 1: Bulk Data Upload

```bash
set -euo pipefail
DATASET=ri.foundry.main.dataset.abc123

# The simplest form: one managed transaction for the whole directory
pltr dataset files upload ./csv-exports "$DATASET"
```

The same with a transaction you control:

```bash
TRANSACTION=$(pltr dataset transactions start "$DATASET" --type APPEND \
  --format json | jq -r '.rid')

for file in *.csv; do
  pltr dataset files upload "$file" "$DATASET" --transaction-rid "$TRANSACTION"
done

pltr dataset transactions commit "$DATASET" "$TRANSACTION"
```

### Example 2: Safe Dataset Update with Validation

```bash
DATASET=ri.foundry.main.dataset.abc123
TRANSACTION=$(pltr dataset transactions start "$DATASET" --type UPDATE \
  --format json | jq -r '.rid')

pltr dataset files upload updated_data.csv "$DATASET" --transaction-rid "$TRANSACTION"

if validate_dataset.sh "$DATASET" "$TRANSACTION"; then
  pltr dataset transactions commit "$DATASET" "$TRANSACTION"
  echo "Dataset updated"
else
  pltr dataset transactions abort "$DATASET" "$TRANSACTION" --yes
  echo "Update aborted: validation failed"
fi
```

### Example 3: Atomic Multi-File Replacement

```bash
DATASET=ri.foundry.main.dataset.abc123
TRANSACTION=$(pltr dataset transactions start "$DATASET" --type SNAPSHOT \
  --format json | jq -r '.rid')

pltr dataset files upload metadata.json "$DATASET" --transaction-rid "$TRANSACTION"
pltr dataset files upload data_2024.csv "$DATASET" --transaction-rid "$TRANSACTION"
pltr dataset files upload summary.txt "$DATASET" --transaction-rid "$TRANSACTION"

# Replace the dataset's files atomically
pltr dataset transactions commit "$DATASET" "$TRANSACTION"
```

## Best Practices

1. **Prefer managed uploads.** `pltr dataset files upload <directory>` gives you one
   atomic change without bookkeeping.
2. **Use one transaction for multi-step changes**, so they become visible together
   and can be rolled back together.
3. **Pick the right type.** APPEND to add, UPDATE to add or replace, SNAPSHOT to
   replace everything, DELETE to remove files.
4. **Always abort on failure.** An open transaction blocks new transactions on its
   branch; abort it if a step fails.

## Error Handling

Failures print an error on stderr and exit with a documented code. With
`--format json` the last stderr line is a JSON object with the Foundry
`errorName`, `statusCode` and `parameters`.

| Situation | errorName | Exit code |
|---|---|---|
| A transaction is already open on the branch | `OpenTransactionAlreadyExists` | 7 (conflict) |
| The transaction doesn't exist | `TransactionNotFound` | 5 |
| The transaction is already committed or aborted | `TransactionNotOpen` | 6 |
| `--branch` and `--transaction-rid` together on upload | `InvalidParameterCombination` | 6 (pltr refuses it first: 2) |
| No write access to the dataset | e.g. `CreateTransactionPermissionDenied` | 4 |
| Missing or invalid credentials | | 3 |

If a managed directory upload fails, pltr aborts its transaction and says so on
stderr; if even the abort fails, it prints the `pltr dataset transactions abort`
command to run.

## Integration with CI/CD

Example GitHub Actions step (pltr reads credentials from `FOUNDRY_HOST` and
`FOUNDRY_TOKEN`, or `FOUNDRY_CLIENT_ID` and `FOUNDRY_CLIENT_SECRET`):

```yaml
- name: Upload data to Foundry
  env:
    FOUNDRY_HOST: ${{ vars.FOUNDRY_HOST }}
    FOUNDRY_TOKEN: ${{ secrets.FOUNDRY_TOKEN }}
  run: |
    # One managed transaction: committed on success, aborted on failure
    pltr dataset files upload build/output "$DATASET_RID" --path output
```

## Related Commands

- `pltr dataset get`: Get a dataset's metadata
- `pltr dataset branches list`: List a dataset's branches
- `pltr dataset files list`: List files (filter with `--path-prefix`)
- `pltr dataset files upload`: Upload files or directories
- `pltr dataset files get`: Download files, or folders with `--recursive`

## Technical Details

### Transaction States
- **OPEN**: Accepting changes
- **COMMITTED**: Changes applied
- **ABORTED**: Changes discarded

### Concurrency
- A branch has at most one open transaction
- Transactions on different branches are independent
