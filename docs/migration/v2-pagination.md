# Migration Guide: v2.0 Pagination Changes

This guide helps you migrate scripts and workflows from v1.x to v2.0, which introduces pagination controls and a breaking change in default behavior.

## Breaking Change Summary

**Default behavior has changed**: Commands now fetch **only the first page** by default instead of all pages.

| Version | Command | Behavior |
|---------|---------|----------|
| v1.x | `pltr admin user list` | Fetches **all** users |
| v2.0 | `pltr admin user list` | Fetches **first page** only |
| v2.0 | `pltr admin user list --all` | Fetches **all** users (old behavior) |

## Why This Change?

1. **Prevents accidental large fetches**: Users won't accidentally request thousands of items
2. **Improves performance**: Faster initial responses
3. **Better memory usage**: Controlled memory consumption
4. **Industry standard**: Most CLIs paginate by default

## Affected Commands

The following commands have changed default behavior:

- `pltr admin user list`
- `pltr orchestration builds search`
- `pltr ontology object-list`
- `pltr dataset files list` (NEW: previously had no pagination support)

## Migration Steps

### Step 1: Identify Affected Scripts

Search your scripts for commands that relied on fetching all results:

```bash
# Find scripts using affected commands
grep -r "pltr admin user list" ~/scripts/
grep -r "pltr orchestration builds" ~/scripts/
grep -r "pltr dataset files list" ~/scripts/
```

### Step 2: Update Commands

Add the `--all` flag to commands that need all results:

#### Before (v1.x)
```bash
# Fetched all users
pltr admin user list --format json > all_users.json

# Fetched all builds
pltr orchestration builds search > builds.txt

# Fetched all files
pltr dataset files list DATASET_RID > files.txt
```

#### After (v2.0)
```bash
# Add --all to fetch all users
pltr admin user list --all --format json > all_users.json

# Add --all to fetch all builds
pltr orchestration builds search --all > builds.txt

# Add --all to fetch all files
pltr dataset files list DATASET_RID --all > files.txt
```

### Step 3: Consider Pagination for Large Datasets

For very large datasets, consider using pagination instead of `--all`:

#### Before (v1.x)
```bash
# This might timeout or run out of memory
pltr admin user list --format json > users.json
```

#### After (v2.0) - Option 1: Keep old behavior
```bash
# Same as before, but explicit
pltr admin user list --all --format json > users.json
```

#### After (v2.0) - Option 2: Use pagination (better)
```bash
# Fetch in controlled batches
pltr admin user list --page-size 100 --max-pages 10 --format json > users_batch1.json
```

### Step 4: Update Scripts That Process Results

If your scripts expect complete datasets, ensure they fetch all pages:

#### Before (v1.x)
```bash
#!/bin/bash
# Get all users and count them
USERS=$(pltr admin user list --format json)
COUNT=$(echo "$USERS" | jq '.data | length')
echo "Total users: $COUNT"
```

#### After (v2.0) - Fixed
```bash
#!/bin/bash
# Get all users and count them
USERS=$(pltr admin user list --all --format json)
COUNT=$(echo "$USERS" | jq '.data | length')
echo "Total users: $COUNT"
```

Or better, use the pagination metadata:

```bash
#!/bin/bash
# Get all users and count them (with pagination awareness)
USERS=$(pltr admin user list --all --format json)
COUNT=$(echo "$USERS" | jq '.pagination.items_count')
echo "Total users: $COUNT"
```

## Command-Specific Migration

### Admin Commands

#### `pltr admin user list`

**v1.x Behavior:**
```bash
# Fetched all users
pltr admin user list
```

**v2.0 Migration:**
```bash
# Option 1: Get all users (old behavior)
pltr admin user list --all

# Option 2: Use pagination (recommended for large orgs)
pltr admin user list --page-size 100 --max-pages 5
```

**New Capabilities:**
```bash
# Resume from specific page
pltr admin user list --page-token abc123

# Fetch specific number of pages
pltr admin user list --max-pages 3
```

### Orchestration Commands

#### `pltr orchestration builds search`

**v1.x Behavior:**
```bash
# Previously BROKEN: told users to use --page-token but it didn't exist
pltr orchestration builds search
```

**v2.0 Migration:**
```bash
# Now fixed and paginated by default
pltr orchestration builds search

# Get all builds
pltr orchestration builds search --all

# Resume from token (NOW WORKS!)
pltr orchestration builds search --page-token xyz789
```

**Critical Fix:** The `--page-token` parameter is now properly supported!

### Ontology Commands

#### `pltr ontology object-list`

**v1.x Behavior:**
```bash
# Had --page-size but fetched all pages
pltr ontology object-list ONTOLOGY_RID ObjectType --page-size 50
```

**v2.0 Migration:**
```bash
# Now fetches only first page
pltr ontology object-list ONTOLOGY_RID ObjectType --page-size 50

# To fetch all
pltr ontology object-list ONTOLOGY_RID ObjectType --page-size 50 --all

# Or control pages
pltr ontology object-list ONTOLOGY_RID ObjectType --max-pages 5
```

### Dataset Commands

#### `pltr dataset files list`

**v1.x Behavior:**
```bash
# Had NO pagination support - fetched everything at once
# Could timeout or crash on large directories
pltr dataset files list DATASET_RID
```

**v2.0 Migration:**
```bash
# Now paginated by default (safe for large directories!)
pltr dataset files list DATASET_RID

# To fetch all files
pltr dataset files list DATASET_RID --all

# Recommended for large datasets
pltr dataset files list DATASET_RID --page-size 200 --max-pages 10
```

**Critical Improvement:** This command now has pagination support, preventing timeouts and memory issues with large datasets.

## Advanced Migration Patterns

### Pattern 1: Incremental Processing

Instead of loading all data at once, process incrementally:

**Before (v1.x):**
```bash
#!/bin/bash
# Load all users, then process
USERS=$(pltr admin user list --format json)
echo "$USERS" | jq -r '.data[] | .username' | while read user; do
  # Process each user
  echo "Processing: $user"
done
```

**After (v2.0):**
```bash
#!/bin/bash
# Process page by page (better memory usage)
TOKEN=""
PAGE=1

while true; do
  echo "Processing page $PAGE..."

  RESPONSE=$(pltr admin user list --format json --page-size 100 --page-token "$TOKEN")

  # Process this page
  echo "$RESPONSE" | jq -r '.data[] | .username' | while read user; do
    echo "Processing: $user"
  done

  # Check if more pages
  HAS_MORE=$(echo "$RESPONSE" | jq -r '.pagination.has_more')
  if [ "$HAS_MORE" != "true" ]; then
    break
  fi

  # Get next token
  TOKEN=$(echo "$RESPONSE" | jq -r '.pagination.next_page_token')
  PAGE=$((PAGE + 1))
done
```

### Pattern 2: Caching with Resume

For long-running operations, cache results and resume if interrupted:

```bash
#!/bin/bash
# Cache file to track progress
CACHE_FILE=".pagination_cache"

# Load last token if exists
if [ -f "$CACHE_FILE" ]; then
  LAST_TOKEN=$(cat "$CACHE_FILE")
  echo "Resuming from token: $LAST_TOKEN"
else
  LAST_TOKEN=""
fi

# Fetch with resume capability
pltr admin user list --page-token "$LAST_TOKEN" --all --format json > users.json

# Save last token (extract from response if interrupted)
# ... implementation details ...
```

### Pattern 3: Parallel Processing

Process different datasets in parallel:

```bash
#!/bin/bash
# Process different datasets in parallel
pltr admin user list --all > users.txt &
pltr orchestration builds search --all > builds.txt &
wait
```

## Testing Your Migration

### 1. Test with Small Datasets First

```bash
# Test with limited pages
pltr admin user list --max-pages 1

# Verify output looks correct
pltr admin user list --max-pages 1 --format json | jq '.pagination'
```

### 2. Compare Results

Verify you get the same data:

```bash
# v1.x (or v2.0 with --all)
pltr admin user list --all --format json > v1_users.json

# v2.0 with pagination
pltr admin user list --max-pages 100 --format json > v2_users.json

# Compare (should be identical if all pages fetched)
diff <(jq -S '.data' v1_users.json) <(jq -S '.data' v2_users.json)
```

### 3. Monitor Performance

Check if pagination improves performance:

```bash
# Time the old way
time pltr dataset files list DATASET_RID --all

# Time with pagination
time pltr dataset files list DATASET_RID --max-pages 5

# First page should be much faster
time pltr dataset files list DATASET_RID --max-pages 1
```

## Rollback Plan

If you need to temporarily revert to v1.x behavior:

### Option 1: Use --all Everywhere

Create a wrapper script:

```bash
#!/bin/bash
# pltr-v1-compat

if [[ "$@" =~ "user list" ]] || [[ "$@" =~ "builds search" ]]; then
  # Add --all flag automatically
  pltr "$@" --all
else
  pltr "$@"
fi
```

### Option 2: Downgrade

```bash
# Downgrade to v1.x
uv pip install "pltr-cli<2.0.0"
```

## Common Migration Issues

### Issue 1: Scripts Expect Complete Datasets

**Symptom:** Scripts process partial data

**Solution:** Add `--all` flag

```bash
# Before
pltr admin user list | grep "admin"

# After
pltr admin user list --all | grep "admin"
```

### Issue 2: JSON Processing Assumes All Data

**Symptom:** Counts or aggregations are wrong

**Solution:** Use pagination metadata

```bash
# Before (assumed all data)
COUNT=$(pltr admin user list --format json | jq '.data | length')

# After (check pagination)
RESPONSE=$(pltr admin user list --all --format json)
COUNT=$(echo "$RESPONSE" | jq '.pagination.items_count')
```

### Issue 3: Memory Issues with --all

**Symptom:** Out of memory errors with `--all` flag

**Solution:** Use pagination instead

```bash
# Instead of
pltr dataset files list HUGE_DATASET --all

# Use
pltr dataset files list HUGE_DATASET --page-size 100 --max-pages 10

# Process incrementally or save to file
pltr dataset files list HUGE_DATASET --all --output files.json
```

### Issue 4: Timeout on Large Datasets

**Symptom:** Command times out when using `--all`

**Solution:** Fetch in smaller batches

```bash
# Instead of one large --all request
pltr admin user list --all

# Break into multiple smaller requests
for i in {1..10}; do
  pltr admin user list --page-size 100 --max-pages 1 --page-token "$TOKEN"
  # Extract and update TOKEN...
done
```

## Benefits of Migration

After migrating to v2.0 pagination:

1. **Better Performance**: Faster initial responses
2. **Lower Memory Usage**: Fetch only what you need
3. **Resumable Operations**: Can resume interrupted fetches
4. **Better UX**: Clear indication of pagination state
5. **More Control**: Fine-grained control over data fetching

## Getting Help

If you encounter migration issues:

1. Check the [Pagination Guide](../pagination.md)
2. Review command help: `pltr admin user list --help`
3. Test with `--max-pages 1` first
4. Report issues: https://github.com/anthropics/pltr-cli/issues

## Checklist

Use this checklist to track your migration:

- [ ] Identified all scripts using affected commands
- [ ] Added `--all` flag where complete datasets are needed
- [ ] Tested scripts with v2.0 CLI
- [ ] Considered using pagination for large datasets
- [ ] Updated documentation/runbooks
- [ ] Verified output formats haven't changed (beyond pagination metadata)
- [ ] Tested error handling with new pagination flags
- [ ] Updated CI/CD pipelines if applicable
- [ ] Communicated changes to team

## Summary

The v2.0 pagination changes provide better control and performance, but require updating scripts that relied on the old "fetch all" default behavior. Add `--all` to maintain compatibility, or better yet, embrace pagination for improved performance and reliability.
