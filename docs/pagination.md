# Pagination Guide

The `pltr` CLI provides comprehensive pagination support for commands that return large result sets. This guide explains how to use pagination features effectively.

## Overview

Pagination helps you:
- **Control memory usage**: Fetch only what you need
- **Improve performance**: Faster initial responses
- **Resume operations**: Continue from where you left off
- **Handle large datasets**: Work with datasets that would timeout or crash without pagination

## Pagination Flags

All pagination-enabled commands support these flags:

### `--page-size <N>`

Controls the number of items returned per page.

```bash
# Fetch 50 users per page
pltr admin user list --page-size 50

# Fetch 100 builds per page
pltr orchestration builds search --page-size 100
```

**Default**: Uses the value from your settings (typically 20)

### `--max-pages <N>`

Limits the total number of pages to fetch.

```bash
# Fetch only the first page (default)
pltr admin user list --max-pages 1

# Fetch first 3 pages
pltr dataset files list DATASET_RID --max-pages 3
```

**Default**: `1` (fetches only first page)

**⚠️ BREAKING CHANGE**: Previously, commands fetched all pages by default. Now you must explicitly use `--all` to fetch all pages.

### `--page-token <token>`

Resumes fetching from a specific page using a token from a previous response.

```bash
# First request
pltr admin user list --page-size 20

# Output shows: "Next page: --page-token abc123..."

# Resume from that page
pltr admin user list --page-size 20 --page-token abc123
```

**Availability**:
- ✅ **Available**: `admin user list`, `orchestration builds search`
- ⚠️ **Limited**: `ontology object-list`, `dataset files list` (uses SDK's iterator pagination)

### `--all`

Fetches all available pages, overriding `--max-pages`.

```bash
# Fetch all users (may take a while for large organizations)
pltr admin user list --all

# Fetch all files in dataset
pltr dataset files list DATASET_RID --all
```

**Use with caution**: For very large datasets, this can consume significant memory and time.

## Supported Commands

### Admin Commands

#### `pltr admin user list`

List users in your organization with pagination.

```bash
# Default: first page only
pltr admin user list

# List all users
pltr admin user list --all

# List first 5 pages with 100 users each
pltr admin user list --page-size 100 --max-pages 5

# Resume from a specific page
pltr admin user list --page-token abc123
```

**Pagination Type**: Response-based (supports `--page-token`)

### Orchestration Commands

#### `pltr orchestration builds search`

Search for builds with pagination.

```bash
# Default: first page only
pltr orchestration builds search

# Search all builds
pltr orchestration builds search --all

# Search with custom page size
pltr orchestration builds search --page-size 50

# Resume from previous search
pltr orchestration builds search --page-token xyz789
```

**Pagination Type**: Response-based (supports `--page-token`)

### Ontology Commands

#### `pltr ontology object-list`

List objects of a specific type with pagination.

```bash
# Default: first page only
pltr ontology object-list ONTOLOGY_RID ObjectType

# List all objects
pltr ontology object-list ONTOLOGY_RID ObjectType --all

# List first 3 pages
pltr ontology object-list ONTOLOGY_RID ObjectType --max-pages 3

# Custom page size
pltr ontology object-list ONTOLOGY_RID ObjectType --page-size 100 --all
```

**Pagination Type**: Iterator-based (SDK handles token internally)

**Note**: The SDK's `ResourceIterator` manages pagination tokens automatically. You can use `--page-token` if the SDK provides one, but resumption may require re-fetching earlier pages.

### Dataset Commands

#### `pltr dataset files list`

List files in a dataset with pagination.

```bash
# Default: first page only (critical for large datasets!)
pltr dataset files list DATASET_RID

# List all files
pltr dataset files list DATASET_RID --all

# List first 5 pages from specific branch
pltr dataset files list DATASET_RID --branch dev --max-pages 5

# Custom page size
pltr dataset files list DATASET_RID --page-size 200 --all
```

**Pagination Type**: Iterator-based (SDK handles token internally)

**⚠️ Important**: This command previously had NO pagination support. Without `--max-pages` or `--all`, you'll only see the first page of files.

## Output Formats

### Table Format (Default)

When using table format, pagination information is displayed after the table:

```bash
$ pltr admin user list --page-size 5

# ... table output ...

Fetched 5 items (page 1)
Next page: --page-token abc123
Fetch all: Add --all flag
```

### JSON Format

When using JSON format, pagination metadata is included in the output:

```bash
$ pltr admin user list --format json --page-size 5

{
  "data": [
    { "id": "user1", "username": "alice" },
    { "id": "user2", "username": "bob" },
    ...
  ],
  "pagination": {
    "page": 1,
    "items_count": 5,
    "has_more": true,
    "total_pages_fetched": 1,
    "next_page_token": "abc123"
  }
}
```

You can parse this JSON to extract the `next_page_token` for resuming:

```bash
# Extract next page token
TOKEN=$(pltr admin user list --format json | jq -r '.pagination.next_page_token')

# Use it for next page
pltr admin user list --page-token "$TOKEN" --format json
```

### CSV Format

CSV format includes data only (no pagination metadata in the file). Pagination info is printed to the console.

## Best Practices

### 1. Start with Small Page Sizes

When exploring a new dataset, start with a small `--max-pages`:

```bash
# Peek at first page
pltr dataset files list DATASET_RID --max-pages 1

# If looks good, fetch more
pltr dataset files list DATASET_RID --max-pages 5
```

### 2. Use --all Judiciously

Only use `--all` when you need all data:

```bash
# ❌ Dangerous for large datasets
pltr admin user list --all

# ✅ Better: paginate and process incrementally
pltr admin user list --page-size 100 --max-pages 10
```

### 3. Save Large Results to Files

For large datasets, save to file instead of printing to console:

```bash
# Save all users to JSON file
pltr admin user list --all --format json --output users.json

# Save all files list to CSV
pltr dataset files list DATASET_RID --all --format csv --output files.csv
```

### 4. Combine with grep/jq for Filtering

Process pages incrementally:

```bash
# Find users matching pattern across pages
for i in {1..5}; do
  pltr admin user list --page-size 100 --max-pages 1 --page-token "$TOKEN" \
    | grep "pattern"
  # Extract next token...
done
```

### 5. Script with JSON Format

Use JSON format for scripting:

```bash
#!/bin/bash
TOKEN=""
TOTAL=0

while true; do
  RESPONSE=$(pltr admin user list --format json --page-size 100 --page-token "$TOKEN")

  # Process data
  ITEMS=$(echo "$RESPONSE" | jq '.data | length')
  TOTAL=$((TOTAL + ITEMS))

  # Check if more pages
  HAS_MORE=$(echo "$RESPONSE" | jq -r '.pagination.has_more')
  if [ "$HAS_MORE" != "true" ]; then
    break
  fi

  # Get next token
  TOKEN=$(echo "$RESPONSE" | jq -r '.pagination.next_page_token')
done

echo "Total items: $TOTAL"
```

## Pagination Patterns

### Pattern 1: Fetch All at Once

For smaller datasets where you need all data:

```bash
pltr admin user list --all --format json --output all_users.json
```

### Pattern 2: Page Through Results

For exploring large datasets:

```bash
# Page 1
pltr ontology object-list ONTOLOGY_RID ObjectType --page-size 50

# Review, then page 2
pltr ontology object-list ONTOLOGY_RID ObjectType --page-size 50 --max-pages 2

# Continue as needed...
```

### Pattern 3: Resume Interrupted Operations

If a long-running operation is interrupted:

```bash
# Start fetching (get interrupted)
pltr dataset files list DATASET_RID --all > files.txt

# Note the last token from output
# Resume from that token
pltr dataset files list DATASET_RID --page-token last_token --all >> files.txt
```

## Troubleshooting

### "No more pages available"

This means you've reached the end of the data. There are no more items to fetch.

### "Next page: Use --max-pages N"

For iterator-based commands, increase `--max-pages` to fetch more:

```bash
# If you see this, increment max-pages
pltr ontology object-list ONTOLOGY_RID ObjectType --max-pages 5
```

### Memory Issues

If you're running out of memory:

1. Reduce `--page-size`:
   ```bash
   pltr admin user list --page-size 10 --all
   ```

2. Process in smaller batches:
   ```bash
   # Process first 1000 users
   pltr admin user list --page-size 100 --max-pages 10
   ```

3. Save to file instead of viewing:
   ```bash
   pltr admin user list --all --output users.json
   ```

### "Cannot resume with --page-token (SDK limitation)"

This warning appears for iterator-based commands. The SDK's `ResourceIterator` may not support explicit token-based resumption. You can still use `--max-pages` to fetch more data.

## Performance Tips

1. **Parallel fetching**: For different queries, run them in parallel
   ```bash
   pltr admin user list --all > users.txt &
   pltr orchestration builds search --all > builds.txt &
   wait
   ```

2. **Batch processing**: Process each page as it arrives instead of waiting for all pages

3. **Appropriate page sizes**:
   - Small items (users, groups): 100-500 per page
   - Large items (files with metadata): 20-50 per page

4. **Use filters when available**: Reduce the dataset size before paginating

## SDK Pagination Patterns

The `pltr` CLI works with two SDK pagination patterns:

### Response-Based Pagination

Used by: `admin user list`, `orchestration builds search`

- SDK returns response objects with explicit `.data` and `.next_page_token`
- Full support for `--page-token` resumption
- Most reliable for interrupted operations

### Iterator-Based Pagination

Used by: `ontology object-list`, `dataset files list`

- SDK returns `ResourceIterator` that auto-paginates
- SDK manages tokens internally via `.next_page_token` property
- Resume capability depends on SDK implementation
- Use `--max-pages` to control fetching

Both patterns are fully supported by `pltr` CLI, with appropriate handling for each.

## Related Settings

Configure default pagination behavior in your settings:

```bash
# View current settings
pltr config show

# Settings that affect pagination:
# - page_size: Default items per page (default: 20)
```

## Examples

### Example 1: Export All Users

```bash
# Export all users to JSON with all available data
pltr admin user list --all --format json --output all_users.json

# Check how many users were fetched
jq '.pagination.items_count' all_users.json
```

### Example 2: Search Large Build History

```bash
# Search builds, fetching 5 pages at a time
TOKEN=""
for i in {1..5}; do
  pltr orchestration builds search \
    --page-size 50 \
    --page-token "$TOKEN" \
    --format json

  # Extract next token for next iteration
  # ... (implementation details)
done
```

### Example 3: List Files from Large Dataset

```bash
# List first 100 files to understand structure
pltr dataset files list DATASET_RID --page-size 100 --max-pages 1

# After confirming structure, get all files
pltr dataset files list DATASET_RID --all --format csv --output files.csv

# Count files
wc -l files.csv
```

## Migration from Previous Versions

**⚠️ BREAKING CHANGE**: The default behavior has changed.

### Before (v1.x)
```bash
# This fetched ALL users
pltr admin user list
```

### After (v2.x)
```bash
# This fetches only first page
pltr admin user list

# To get ALL users, use --all
pltr admin user list --all
```

See [Migration Guide](migration/v2-pagination.md) for detailed migration instructions.
