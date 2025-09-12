# CSV Upload Examples

Complete examples for uploading CSV files to Foundry datasets using pltr-cli.

## Prerequisites

- pltr-cli installed and configured
- Authentication set up (see [Quick Start Guide](../user-guide/quick-start.md))
- Write permissions to create/modify datasets in Foundry

## 📤 Simple CSV Upload to New Dataset

### Step 1: Create a Dataset and Upload CSV

```bash
#!/bin/bash
# upload_csv_simple.sh - Simple CSV upload to new dataset

CSV_FILE="data.csv"
DATASET_NAME="sales_data_$(date +%Y%m%d)"
PARENT_FOLDER="ri.foundry.main.folder.your-folder-rid"  # Replace with your folder RID

echo "Creating new dataset: $DATASET_NAME"

# Create the dataset
DATASET_RID=$(pltr dataset create "$DATASET_NAME" \
  --parent-folder "$PARENT_FOLDER" \
  --format json | jq -r '.rid')

echo "Created dataset: $DATASET_RID"

# Start a transaction
echo "Starting transaction..."
TRANSACTION_RID=$(pltr dataset transaction create "$DATASET_RID" \
  --format json | jq -r '.rid')

echo "Transaction started: $TRANSACTION_RID"

# Upload the CSV file
echo "Uploading CSV file..."
pltr dataset files upload "$CSV_FILE" "$DATASET_RID" \
  --transaction-rid "$TRANSACTION_RID"

# Commit the transaction
echo "Committing transaction..."
pltr dataset transaction commit "$DATASET_RID" "$TRANSACTION_RID"

echo "✅ CSV uploaded successfully to dataset: $DATASET_RID"

# Apply/infer the schema automatically (NEW!)
echo "Applying schema to dataset..."
pltr dataset schema apply "$DATASET_RID"

echo "✅ Schema applied successfully"
```

### Step 2: Verify Upload

```bash
# Check dataset info
pltr dataset get "$DATASET_RID"

# List files in dataset
pltr dataset files list "$DATASET_RID"

# Check the applied schema (NEW!)
pltr dataset schema get "$DATASET_RID"

# Query the data (now with proper types!)
pltr sql execute "SELECT COUNT(*) as row_count FROM \`$DATASET_RID\`"
```

## 📊 Upload Multiple CSV Files

### Batch Upload Script

```bash
#!/bin/bash
# batch_csv_upload.sh - Upload multiple CSV files to a dataset

DATASET_RID="ri.foundry.main.dataset.your-dataset-rid"
CSV_DIR="./csv_files"

# Start transaction
echo "Starting transaction for batch upload..."
TRANSACTION_RID=$(pltr dataset transaction create "$DATASET_RID" \
  --format json | jq -r '.rid')

# Upload all CSV files
for csv_file in "$CSV_DIR"/*.csv; do
  if [ -f "$csv_file" ]; then
    filename=$(basename "$csv_file")
    echo "Uploading $filename..."

    pltr dataset files upload "$csv_file" "$DATASET_RID" \
      --transaction-rid "$TRANSACTION_RID" \
      --branch "master"

    if [ $? -eq 0 ]; then
      echo "✅ $filename uploaded"
    else
      echo "❌ Failed to upload $filename"
      # Optionally abort transaction on failure
      pltr dataset transaction abort "$DATASET_RID" "$TRANSACTION_RID"
      exit 1
    fi
  fi
done

# Commit all uploads
echo "Committing transaction..."
pltr dataset transaction commit "$DATASET_RID" "$TRANSACTION_RID"

echo "✅ All CSV files uploaded successfully"
```

## 🔄 Update Existing Dataset with New CSV

### Replace Dataset Contents

```bash
#!/bin/bash
# update_dataset.sh - Replace dataset contents with new CSV

DATASET_RID="ri.foundry.main.dataset.your-dataset-rid"
NEW_CSV="updated_data.csv"

# Create a snapshot transaction (preserves history)
echo "Creating snapshot transaction..."
TRANSACTION_RID=$(pltr dataset transaction create "$DATASET_RID" \
  --transaction-type "SNAPSHOT" \
  --format json | jq -r '.rid')

# Clear existing files (optional - for full replacement)
echo "Clearing existing files..."
pltr dataset files delete-all "$DATASET_RID" \
  --transaction-rid "$TRANSACTION_RID"

# Upload new CSV
echo "Uploading new CSV..."
pltr dataset files upload "$NEW_CSV" "$DATASET_RID" \
  --transaction-rid "$TRANSACTION_RID"

# Commit changes
echo "Committing changes..."
pltr dataset transaction commit "$DATASET_RID" "$TRANSACTION_RID" \
  --message "Updated dataset with new CSV data"

echo "✅ Dataset updated successfully"
```

## 🔧 Schema Management for CSV Datasets

### Automatic Schema Inference

When uploading CSV files, pltr-cli can automatically infer the schema from your CSV headers and data:

```bash
#!/bin/bash
# infer_schema.sh - Automatically set schema from CSV

CSV_FILE="sales_data.csv"
DATASET_RID="ri.foundry.main.dataset.your-dataset-rid"

# Infer and set schema from CSV
pltr dataset schema set "$DATASET_RID" --from-csv "$CSV_FILE"

# View the inferred schema
pltr dataset schema get "$DATASET_RID" --format json
```

The schema inference will:
- Detect column names from CSV headers
- Analyze sample rows to determine data types
- Support types: STRING, INTEGER, DOUBLE, DATE, BOOLEAN, TIMESTAMP
- Mark columns as nullable if empty values are found

### Manual Schema Definition

For precise control, you can define the schema manually:

```bash
# Define schema using JSON
SCHEMA_JSON='{
  "fields": [
    {"name": "id", "type": "INTEGER", "nullable": false},
    {"name": "name", "type": "STRING", "nullable": false},
    {"name": "email", "type": "STRING", "nullable": true},
    {"name": "amount", "type": "DOUBLE", "nullable": false},
    {"name": "created_date", "type": "DATE", "nullable": false},
    {"name": "is_active", "type": "BOOLEAN", "nullable": false}
  ]
}'

pltr dataset schema set "$DATASET_RID" --json "$SCHEMA_JSON"
```

Or load from a JSON file:

```bash
# schema.json
cat > schema.json << 'EOF'
{
  "fields": [
    {"name": "product_id", "type": "INTEGER", "nullable": false},
    {"name": "product_name", "type": "STRING", "nullable": false},
    {"name": "price", "type": "DOUBLE", "nullable": false},
    {"name": "in_stock", "type": "BOOLEAN", "nullable": false},
    {"name": "last_updated", "type": "TIMESTAMP", "nullable": true}
  ]
}
EOF

pltr dataset schema set "$DATASET_RID" --json-file schema.json
```

### Recommended Schema-Aware CSV Upload Workflow

Here's the recommended workflow for uploading CSV with automatic schema application:

```bash
#!/bin/bash
# complete_csv_upload.sh - Upload CSV with automatic schema

CSV_FILE="data.csv"
DATASET_NAME="typed_dataset_$(date +%Y%m%d)"
PARENT_FOLDER="ri.foundry.main.folder.your-folder-rid"

# 1. Create dataset
DATASET_RID=$(pltr dataset create "$DATASET_NAME" \
  --parent-folder "$PARENT_FOLDER" \
  --format json | jq -r '.rid')

# 2. Upload CSV file
TRANSACTION_RID=$(pltr dataset transaction create "$DATASET_RID" \
  --format json | jq -r '.rid')

pltr dataset files upload "$CSV_FILE" "$DATASET_RID" \
  --transaction-rid "$TRANSACTION_RID"

pltr dataset transaction commit "$DATASET_RID" "$TRANSACTION_RID"

# 3. Apply schema automatically
pltr dataset schema apply "$DATASET_RID"

# 4. Verify applied schema
echo "Dataset schema:"
pltr dataset schema get "$DATASET_RID"

# 5. Query with proper types
pltr sql execute "
  SELECT
    COUNT(*) as total_rows,
    AVG(amount) as avg_amount,
    MAX(created_date) as latest_date
  FROM \`$DATASET_RID\`
"
```

## 📝 CSV with Schema Validation

### Upload with Schema Check

```bash
#!/bin/bash
# csv_with_schema.sh - Upload CSV and validate schema

CSV_FILE="structured_data.csv"
DATASET_RID="ri.foundry.main.dataset.your-dataset-rid"
EXPECTED_COLUMNS="id,name,email,created_date,amount"

# Function to validate CSV headers
validate_csv_schema() {
  local csv_file=$1
  local expected=$2

  # Get CSV headers
  headers=$(head -n 1 "$csv_file" | tr '[:upper:]' '[:lower:]')

  # Check if headers match expected
  if [ "$headers" != "$expected" ]; then
    echo "❌ Schema mismatch!"
    echo "Expected: $expected"
    echo "Found: $headers"
    return 1
  fi

  echo "✅ Schema validation passed"
  return 0
}

# Validate before upload
if validate_csv_schema "$CSV_FILE" "$EXPECTED_COLUMNS"; then
  # Start transaction
  TRANSACTION_RID=$(pltr dataset transaction create "$DATASET_RID" \
    --format json | jq -r '.rid')

  # Upload CSV
  pltr dataset files upload "$CSV_FILE" "$DATASET_RID" \
    --transaction-rid "$TRANSACTION_RID"

  # Commit
  pltr dataset transaction commit "$DATASET_RID" "$TRANSACTION_RID"

  echo "✅ CSV uploaded with validated schema"
else
  echo "❌ Upload aborted due to schema mismatch"
  exit 1
fi
```

## 🚀 Advanced: Streaming Large CSV Upload

### Upload Large Files with Progress

```bash
#!/bin/bash
# large_csv_upload.sh - Upload large CSV with progress tracking

CSV_FILE="large_dataset.csv"
DATASET_NAME="large_dataset_$(date +%Y%m%d_%H%M%S)"
PARENT_FOLDER="ri.foundry.main.folder.your-folder-rid"

# Function to get file size in MB
get_file_size_mb() {
  local file=$1
  local size_bytes=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null)
  echo $((size_bytes / 1048576))
}

# Function to monitor upload progress
monitor_upload() {
  local pid=$1
  local file=$2
  local size_mb=$(get_file_size_mb "$file")

  echo "Uploading ${size_mb}MB file..."

  while kill -0 $pid 2>/dev/null; do
    echo -n "."
    sleep 2
  done

  echo ""
  wait $pid
  return $?
}

# Create dataset
echo "Creating dataset for large file..."
DATASET_RID=$(pltr dataset create "$DATASET_NAME" \
  --parent-folder "$PARENT_FOLDER" \
  --format json | jq -r '.rid')

# Start transaction
TRANSACTION_RID=$(pltr dataset transaction create "$DATASET_RID" \
  --format json | jq -r '.rid')

# Upload in background and monitor
{
  pltr dataset files upload "$CSV_FILE" "$DATASET_RID" \
    --transaction-rid "$TRANSACTION_RID"
} &

UPLOAD_PID=$!
monitor_upload $UPLOAD_PID "$CSV_FILE"

if [ $? -eq 0 ]; then
  # Commit transaction
  echo "Committing transaction..."
  pltr dataset transaction commit "$DATASET_RID" "$TRANSACTION_RID"
  echo "✅ Large CSV uploaded successfully"
else
  # Abort on failure
  echo "❌ Upload failed, aborting transaction..."
  pltr dataset transaction abort "$DATASET_RID" "$TRANSACTION_RID"
  exit 1
fi
```

## 🔧 Python Script for CSV Upload

### Using pltr-cli as a Library

```python
#!/usr/bin/env python3
"""
csv_upload.py - Upload CSV to Foundry using pltr-cli as a library
"""

import sys
import pandas as pd
from pathlib import Path
from pltr.auth.manager import AuthManager
from pltr.services.dataset import DatasetService

def upload_csv_to_foundry(csv_path, dataset_name, parent_folder_rid=None):
    """
    Upload a CSV file to Foundry as a new dataset.

    Args:
        csv_path: Path to CSV file
        dataset_name: Name for the new dataset
        parent_folder_rid: Parent folder RID (optional)

    Returns:
        Dataset RID if successful, None otherwise
    """
    try:
        # Initialize authentication
        auth = AuthManager()

        # Create dataset service
        dataset_service = DatasetService(auth)

        # Create new dataset
        print(f"Creating dataset: {dataset_name}")
        dataset = dataset_service.create_dataset(
            name=dataset_name,
            parent_folder_rid=parent_folder_rid
        )
        dataset_rid = dataset['rid']
        print(f"Created dataset: {dataset_rid}")

        # Start transaction
        print("Starting transaction...")
        transaction = dataset_service.create_transaction(dataset_rid)
        transaction_rid = transaction['rid']

        # Upload CSV file
        print(f"Uploading {csv_path}...")
        dataset_service.upload_file(
            dataset_rid=dataset_rid,
            file_path=csv_path,
            transaction_rid=transaction_rid
        )

        # Commit transaction
        print("Committing transaction...")
        dataset_service.commit_transaction(
            dataset_rid=dataset_rid,
            transaction_rid=transaction_rid
        )

        print(f"✅ Successfully uploaded CSV to dataset: {dataset_rid}")
        return dataset_rid

    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def validate_and_upload_csv(csv_path, dataset_name):
    """
    Validate CSV before uploading.
    """
    csv_path = Path(csv_path)

    # Check file exists
    if not csv_path.exists():
        print(f"❌ File not found: {csv_path}")
        return False

    # Validate CSV structure
    try:
        df = pd.read_csv(csv_path)
        print(f"CSV Info:")
        print(f"  - Rows: {len(df)}")
        print(f"  - Columns: {', '.join(df.columns)}")
        print(f"  - Size: {csv_path.stat().st_size / 1048576:.2f} MB")

        # Check for required columns (customize as needed)
        required_columns = []  # Add your required columns
        missing = set(required_columns) - set(df.columns)
        if missing:
            print(f"❌ Missing required columns: {missing}")
            return False

    except Exception as e:
        print(f"❌ Invalid CSV: {e}")
        return False

    # Upload to Foundry
    return upload_csv_to_foundry(csv_path, dataset_name)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python csv_upload.py <csv_file> <dataset_name>")
        sys.exit(1)

    csv_file = sys.argv[1]
    dataset_name = sys.argv[2]

    if validate_and_upload_csv(csv_file, dataset_name):
        sys.exit(0)
    else:
        sys.exit(1)
```

## 🔄 Incremental CSV Updates

### Append New Data to Existing Dataset

```bash
#!/bin/bash
# incremental_update.sh - Append new CSV data to existing dataset

DATASET_RID="ri.foundry.main.dataset.your-dataset-rid"
NEW_DATA_DIR="./daily_updates"
PROCESSED_DIR="./processed"

# Create processed directory if it doesn't exist
mkdir -p "$PROCESSED_DIR"

# Process each new CSV file
for csv_file in "$NEW_DATA_DIR"/*.csv; do
  if [ -f "$csv_file" ]; then
    filename=$(basename "$csv_file")
    timestamp=$(date +%Y%m%d_%H%M%S)

    echo "Processing $filename..."

    # Start transaction for this file
    TRANSACTION_RID=$(pltr dataset transaction create "$DATASET_RID" \
      --transaction-type "APPEND" \
      --format json | jq -r '.rid')

    # Upload with timestamp in filename to avoid conflicts
    target_name="${timestamp}_${filename}"

    pltr dataset files upload "$csv_file" "$DATASET_RID" \
      --transaction-rid "$TRANSACTION_RID" \
      --target-path "$target_name"

    if [ $? -eq 0 ]; then
      # Commit transaction
      pltr dataset transaction commit "$DATASET_RID" "$TRANSACTION_RID" \
        --message "Added $filename"

      # Move to processed
      mv "$csv_file" "$PROCESSED_DIR/"
      echo "✅ $filename processed and moved to $PROCESSED_DIR"
    else
      # Abort transaction on failure
      pltr dataset transaction abort "$DATASET_RID" "$TRANSACTION_RID"
      echo "❌ Failed to process $filename"
    fi
  fi
done

echo "✅ Incremental update complete"
```

## 🛡️ Error Handling and Retry

### Robust Upload with Retry Logic

```bash
#!/bin/bash
# robust_csv_upload.sh - Upload with error handling and retry

CSV_FILE="important_data.csv"
DATASET_RID="ri.foundry.main.dataset.your-dataset-rid"
MAX_RETRIES=3
RETRY_DELAY=10

upload_with_retry() {
  local file=$1
  local dataset=$2
  local attempt=1

  while [ $attempt -le $MAX_RETRIES ]; do
    echo "Upload attempt $attempt of $MAX_RETRIES..."

    # Start transaction
    TRANSACTION_RID=$(pltr dataset transaction create "$dataset" \
      --format json 2>/dev/null | jq -r '.rid')

    if [ -z "$TRANSACTION_RID" ]; then
      echo "Failed to start transaction"
      attempt=$((attempt + 1))
      sleep $RETRY_DELAY
      continue
    fi

    # Try upload
    if pltr dataset files upload "$file" "$dataset" \
      --transaction-rid "$TRANSACTION_RID" 2>/dev/null; then

      # Try commit
      if pltr dataset transaction commit "$dataset" "$TRANSACTION_RID" 2>/dev/null; then
        echo "✅ Upload successful on attempt $attempt"
        return 0
      else
        echo "Commit failed, aborting transaction"
        pltr dataset transaction abort "$dataset" "$TRANSACTION_RID" 2>/dev/null
      fi
    else
      echo "Upload failed, aborting transaction"
      pltr dataset transaction abort "$dataset" "$TRANSACTION_RID" 2>/dev/null
    fi

    attempt=$((attempt + 1))
    if [ $attempt -le $MAX_RETRIES ]; then
      echo "Retrying in $RETRY_DELAY seconds..."
      sleep $RETRY_DELAY
    fi
  done

  echo "❌ Upload failed after $MAX_RETRIES attempts"
  return 1
}

# Main execution
if [ ! -f "$CSV_FILE" ]; then
  echo "❌ CSV file not found: $CSV_FILE"
  exit 1
fi

echo "Starting robust CSV upload..."
if upload_with_retry "$CSV_FILE" "$DATASET_RID"; then
  echo "✅ CSV upload completed successfully"

  # Verify upload
  echo "Verifying upload..."
  pltr dataset files list "$DATASET_RID" --format table
else
  echo "❌ CSV upload failed"
  exit 1
fi
```

## 📊 Tips and Best Practices

### 1. Transaction Management
- Always use transactions for data integrity
- Commit only after successful upload
- Abort transactions on failure to avoid partial uploads

### 2. File Naming
- Use timestamps to avoid naming conflicts
- Organize files in folders within datasets
- Use descriptive names for easier management

### 3. Performance
- For large files (>100MB), consider splitting into chunks
- Use batch uploads for multiple files
- Monitor system resources during upload

### 4. Error Handling
- Implement retry logic for network issues
- Validate data before upload
- Keep logs of successful/failed uploads

### 5. Schema Management
- Validate CSV structure before upload
- Document expected schema
- Handle schema evolution carefully

## 🔍 Troubleshooting

### Common Issues

1. **Authentication Error**
   ```bash
   # Verify authentication
   pltr verify

   # Re-configure if needed
   pltr configure
   ```

2. **Permission Denied**
   - Ensure you have write permissions to the dataset/folder
   - Check with: `pltr dataset get <dataset_rid>`

3. **Transaction Already Exists**
   - List existing transactions: `pltr dataset transaction list <dataset_rid>`
   - Abort stale transactions: `pltr dataset transaction abort <dataset_rid> <transaction_rid>`

4. **File Too Large**
   - Split large CSV files: `split -l 1000000 large.csv part_`
   - Upload parts individually

5. **Network Timeout**
   - Increase timeout in configuration
   - Use retry logic for uploads
   - Consider uploading during off-peak hours

6. **Schema Issues**
   - **Schema not taking effect**: Ensure the dataset has been created and files uploaded before applying schema
   - **Type inference errors**: Review the first 100 rows of your CSV for inconsistent data
   - **Column name issues**: Schema field names must be valid identifiers (no spaces, special chars)
   - **Query errors after schema**: The schema applies to new data; existing data may need reprocessing
   - **Apply vs Set commands**: Use `schema apply` for uploaded data, `schema set --from-csv` for local files

   ```bash
   # Debug schema issues
   # 1. Check current schema
   pltr dataset schema get <dataset_rid>

   # 2. Apply schema from uploaded data (recommended)
   pltr dataset schema apply <dataset_rid>

   # 3. Or set schema from local CSV file (requires preview API)
   pltr dataset schema set <dataset_rid> --from-csv data.csv

   # 4. Verify CSV headers match schema
   head -1 data.csv
   ```

   **When to use which schema command:**
   - **`pltr dataset schema apply`**: Use after uploading files to the dataset. Analyzes uploaded data directly and doesn't require preview API access. This is the **recommended approach**.
   - **`pltr dataset schema set --from-csv`**: Use when you want to infer schema from a local CSV file before uploading. Requires preview API access and may not reflect the exact uploaded data.

## 📚 Related Documentation

- [Dataset Commands Reference](../user-guide/commands.md#dataset-commands)
- [Transaction Management](../user-guide/workflows.md#transaction-management)
- [Authentication Setup](../user-guide/authentication.md)
- [Examples Gallery](gallery.md)

---

💡 **Remember**: Always test your upload scripts with small datasets first before processing large production data!
