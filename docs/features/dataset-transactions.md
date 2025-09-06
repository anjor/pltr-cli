# Dataset Transaction Management

## Overview

pltr-cli provides comprehensive transaction management for Foundry datasets, enabling atomic operations with full rollback capability. This feature allows for safe, multi-step dataset modifications with data integrity guarantees.

## Key Features

- **Atomic Operations**: All changes within a transaction are applied together or not at all
- **Rollback Capability**: Abort transactions to discard all changes
- **Concurrent Modification Handling**: Multiple users can work on different transactions
- **Transaction Types**: Support for APPEND, UPDATE, SNAPSHOT, and DELETE operations
- **Progress Tracking**: Monitor transaction status throughout lifecycle

## Transaction Lifecycle

### 1. Starting a Transaction

```bash
pltr dataset transactions start <dataset-rid> [options]
```

**Options:**
- `--branch <name>`: Target branch (default: master)
- `--type <type>`: Transaction type (APPEND, UPDATE, SNAPSHOT, DELETE)
- `--profile <name>`: Authentication profile to use
- `--format <format>`: Output format (table, json, csv)

**Example:**
```bash
pltr dataset transactions start ri.foundry.main.dataset.abc123 --type APPEND
```

### 2. Performing Operations

Once a transaction is started, you can perform operations within it:

```bash
# Upload files
pltr dataset files upload data.csv ri.foundry.main.dataset.abc123 \
  --transaction-rid ri.foundry.main.transaction.xyz

# Upload multiple files in the same transaction
pltr dataset files upload file1.csv ri.foundry.main.dataset.abc123 \
  --transaction-rid ri.foundry.main.transaction.xyz
pltr dataset files upload file2.csv ri.foundry.main.dataset.abc123 \
  --transaction-rid ri.foundry.main.transaction.xyz
```

### 3. Checking Transaction Status

```bash
pltr dataset transactions status <dataset-rid> <transaction-rid>
```

**Example:**
```bash
pltr dataset transactions status ri.foundry.main.dataset.abc123 \
  ri.foundry.main.transaction.xyz
```

### 4. Committing Changes

```bash
pltr dataset transactions commit <dataset-rid> <transaction-rid>
```

**Example:**
```bash
pltr dataset transactions commit ri.foundry.main.dataset.abc123 \
  ri.foundry.main.transaction.xyz
```

### 5. Aborting a Transaction

```bash
pltr dataset transactions abort <dataset-rid> <transaction-rid> [--yes]
```

**Options:**
- `--yes`: Skip confirmation prompt

**Example:**
```bash
pltr dataset transactions abort ri.foundry.main.dataset.abc123 \
  ri.foundry.main.transaction.xyz --yes
```

## Transaction Types

### APPEND
Adds new files to the dataset without affecting existing files.

```bash
pltr dataset transactions start ri.foundry.main.dataset.abc123 --type APPEND
```

### UPDATE
Adds new files and can overwrite existing files with the same path.

```bash
pltr dataset transactions start ri.foundry.main.dataset.abc123 --type UPDATE
```

### SNAPSHOT
Replaces the entire dataset with a new set of files.

```bash
pltr dataset transactions start ri.foundry.main.dataset.abc123 --type SNAPSHOT
```

### DELETE
Removes specified files from the dataset.

```bash
pltr dataset transactions start ri.foundry.main.dataset.abc123 --type DELETE
```

## Listing Transactions

View all transactions for a dataset:

```bash
pltr dataset transactions list <dataset-rid> [options]
```

**Options:**
- `--branch <name>`: Filter by branch
- `--format <format>`: Output format
- `--output <file>`: Save output to file

**Example:**
```bash
pltr dataset transactions list ri.foundry.main.dataset.abc123 --branch master
```

## Practical Examples

### Example 1: Bulk Data Upload

```bash
# Start an APPEND transaction
TRANSACTION=$(pltr dataset transactions start ri.foundry.main.dataset.abc123 \
  --type APPEND --format json | jq -r '.transaction_rid')

# Upload multiple CSV files
for file in *.csv; do
  pltr dataset files upload "$file" ri.foundry.main.dataset.abc123 \
    --transaction-rid $TRANSACTION
done

# Check status
pltr dataset transactions status ri.foundry.main.dataset.abc123 $TRANSACTION

# Commit if successful
pltr dataset transactions commit ri.foundry.main.dataset.abc123 $TRANSACTION
```

### Example 2: Safe Dataset Update with Validation

```bash
# Start UPDATE transaction
TRANSACTION=$(pltr dataset transactions start ri.foundry.main.dataset.abc123 \
  --type UPDATE --format json | jq -r '.transaction_rid')

# Upload new data
pltr dataset files upload updated_data.csv ri.foundry.main.dataset.abc123 \
  --transaction-rid $TRANSACTION

# Perform validation (custom script)
if validate_dataset.sh ri.foundry.main.dataset.abc123 $TRANSACTION; then
  # Validation passed, commit
  pltr dataset transactions commit ri.foundry.main.dataset.abc123 $TRANSACTION
  echo "Dataset updated successfully"
else
  # Validation failed, abort
  pltr dataset transactions abort ri.foundry.main.dataset.abc123 $TRANSACTION --yes
  echo "Update aborted due to validation failure"
fi
```

### Example 3: Atomic Multi-File Replacement

```bash
# Start SNAPSHOT transaction to replace entire dataset
TRANSACTION=$(pltr dataset transactions start ri.foundry.main.dataset.abc123 \
  --type SNAPSHOT --format json | jq -r '.transaction_rid')

# Upload all new files
pltr dataset files upload metadata.json ri.foundry.main.dataset.abc123 \
  --transaction-rid $TRANSACTION
pltr dataset files upload data_2024.csv ri.foundry.main.dataset.abc123 \
  --transaction-rid $TRANSACTION
pltr dataset files upload summary.txt ri.foundry.main.dataset.abc123 \
  --transaction-rid $TRANSACTION

# Commit to replace dataset atomically
pltr dataset transactions commit ri.foundry.main.dataset.abc123 $TRANSACTION
```

## Best Practices

1. **Always Use Transactions for Multi-File Operations**
   - Ensures atomicity and consistency
   - Allows rollback if any part fails

2. **Check Transaction Status Before Committing**
   - Verify all operations completed successfully
   - Review changes before making them permanent

3. **Use Appropriate Transaction Types**
   - APPEND for adding new data
   - UPDATE for modifying existing data
   - SNAPSHOT for complete replacements
   - DELETE for removing specific files

4. **Handle Errors Gracefully**
   - Always have abort logic for failed operations
   - Log transaction RIDs for debugging

5. **Clean Up Aborted Transactions**
   - Aborted transactions free up resources
   - Don't leave transactions open unnecessarily

## Error Handling

Common errors and solutions:

### Transaction Already Exists
**Error:** "A transaction is already open for this branch"
**Solution:** Commit or abort the existing transaction before starting a new one

### Transaction Not Found
**Error:** "Transaction not found"
**Solution:** Verify the transaction RID and ensure it hasn't been committed/aborted

### Permission Denied
**Error:** "Insufficient permissions to modify dataset"
**Solution:** Ensure your user has write access to the dataset

## Integration with CI/CD

Example GitHub Actions workflow:

```yaml
- name: Upload Data to Foundry
  run: |
    # Start transaction
    TRANSACTION=$(pltr dataset transactions start $DATASET_RID \
      --type APPEND --format json | jq -r '.transaction_rid')

    # Upload artifacts
    pltr dataset files upload build/output.csv $DATASET_RID \
      --transaction-rid $TRANSACTION

    # Commit on success
    if [ $? -eq 0 ]; then
      pltr dataset transactions commit $DATASET_RID $TRANSACTION
    else
      pltr dataset transactions abort $DATASET_RID $TRANSACTION --yes
      exit 1
    fi
```

## Related Commands

- `pltr dataset get`: Get dataset information
- `pltr dataset branches list`: List dataset branches
- `pltr dataset files list`: List files in dataset
- `pltr dataset files upload`: Upload files to dataset
- `pltr dataset files get`: Download files from dataset

## Technical Details

### Transaction States
- **OPEN**: Transaction is active and accepting operations
- **COMMITTED**: Transaction completed successfully, changes applied
- **ABORTED**: Transaction cancelled, all changes discarded

### Concurrency
- Multiple transactions can be open on different branches
- Only one transaction per branch at a time
- Transactions are isolated from each other

### Timeouts
- Transactions may timeout after extended periods of inactivity
- Check your Foundry instance configuration for specific timeout values

## Support

For issues or questions about dataset transactions:
1. Check the error message for specific guidance
2. Verify your permissions on the dataset
3. Consult your Foundry administrator for system-specific configurations
4. Report issues at: https://github.com/anjor/pltr-cli/issues
