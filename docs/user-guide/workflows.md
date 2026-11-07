# Common Workflows

Multi-step tasks with pltr. Every command here is described in the
[Command Reference](commands.md); placeholders such as `<dataset-rid>` stand
for RIDs you look up first. The scripts use `jq` to read pltr's JSON output.

## Explore data

```bash
# Who am I, and which ontologies can I see?
pltr admin user current
pltr ontology list

# An ontology's object types, and one type's properties
pltr ontology object-type-list <ontology>
pltr ontology object-type-get <ontology> Employee

# Objects: a page, one object, linked objects
pltr ontology object-list <ontology> Employee --properties name,department
pltr ontology object-get <ontology> Employee E-12345
pltr ontology object-linked <ontology> Employee E-12345 reportsTo

# Filter and aggregate with the API's JSON shapes
pltr ontology object-search <ontology> Employee \
  --where '{"type": "eq", "field": "department", "value": "Engineering"}'
pltr ontology object-aggregate <ontology> Employee \
  --aggregation '[{"type": "count", "name": "count"}, {"type": "avg", "field": "tenure", "name": "avgTenure"}]' \
  --group-by department

# A dataset: metadata, schema, files and a preview of its rows
pltr dataset get <dataset-rid>
pltr dataset schema get <dataset-rid>
pltr dataset files list <dataset-rid>
pltr dataset preview <dataset-rid> --limit 20
```

## Analyze with SQL

```bash
# Quick checks print a table
pltr sql execute 'SELECT COUNT(*) AS n FROM `<dataset-rid>`'
pltr sql execute 'SELECT * FROM `/My Space/My Project/orders` LIMIT 10'

# Results for other tools
pltr sql execute 'SELECT region, SUM(amount) AS total FROM `<dataset-rid>` GROUP BY region' \
  --format csv --output totals.csv
pltr sql export 'SELECT * FROM `<dataset-rid>` WHERE amount > 1000' large_orders.json

# Long-running queries: submit, do something else, then wait for the rows
QUERY_ID=$(pltr sql submit 'SELECT * FROM `<dataset-rid>`' --format json | jq -r .queryId)
pltr sql status "$QUERY_ID"
pltr sql wait "$QUERY_ID" --timeout 1800 --format json > rows.json
```

Several queries can run at once: submit them all, then `pltr sql wait` for
each ID. A query that fails exits with code 7, and its error is on stderr.

## Load files into a dataset

```bash
# Create the dataset in a project (or a folder inside one)
DATASET=$(pltr dataset create "Sales 2026" --parent-folder <project-rid> --format json | jq -r .rid)

# Upload a directory in one transaction (pltr commits it, or aborts it if
# an upload fails)
pltr dataset files upload ./exports "$DATASET" --path raw

# Or control the transaction yourself
TXN=$(pltr dataset transactions start "$DATASET" --type APPEND --format json | jq -r .rid)
pltr dataset files upload jan.csv "$DATASET" --path raw/jan.csv --transaction-rid "$TXN"
pltr dataset files upload feb.csv "$DATASET" --path raw/feb.csv --transaction-rid "$TXN"
pltr dataset transactions commit "$DATASET" "$TXN"

# Give CSV files a typed schema, then check the rows
pltr dataset schema apply "$DATASET" --yes
pltr dataset preview "$DATASET"
```

See [CSV upload examples](../examples/csv-upload.md) and
[dataset transactions](../features/dataset-transactions.md) for more.

## Builds and schedules

```bash
# Recent failures on master
pltr orchestration builds search --status FAILED --branch master --order-by STARTED_TIME:DESC

# Build a dataset and follow its jobs
BUILD=$(pltr orchestration builds create '{"type": "manual", "targetRids": ["<dataset-rid>"]}' \
  --branch master --format json | jq -r .rid)
pltr orchestration builds get "$BUILD"
pltr orchestration builds jobs "$BUILD"

# A nightly schedule; run it once now to test it
SCHEDULE=$(pltr orchestration schedules create \
  '{"target": {"type": "manual", "targetRids": ["<dataset-rid>"]}}' \
  --name "Nightly build" \
  --trigger '{"type": "time", "cronExpression": "0 2 * * *", "timeZone": "UTC"}' \
  --format json | jq -r .rid)
pltr orchestration schedules run "$SCHEDULE"
pltr orchestration schedules runs "$SCHEDULE"

# Pause it during maintenance
pltr orchestration schedules pause "$SCHEDULE"
pltr orchestration schedules unpause "$SCHEDULE"
```

## Set up a project and its permissions

```bash
# Find the space, create a project and a folder in it
pltr space list
PROJECT=$(pltr project create "Customer Analytics" --space-rid <space-rid> \
  --description "Customer behavior and segmentation" --format json | jq -r .rid)
pltr folder create "Raw data" --parent-folder "$PROJECT"

# Role grants take user and group IDs (UUIDs), not names: look them up
GROUP=$(pltr admin group search data-team --format json | jq -r '.data[0].id')
USER=$(pltr admin user search jane --format json | jq -r '.data[0].id')

# Role IDs come from the space's role set; list the grants in use to see them
pltr resource-role list "$PROJECT" --include-inherited
pltr resource-role grant "$PROJECT" --principal-id "$GROUP" --role <role-id>
pltr resource-role grant "$PROJECT" --principal-id "$USER" --role <role-id>

# Review, then remove a grant
pltr resource-role list "$PROJECT"
pltr resource-role revoke "$PROJECT" --principal-id "$USER" --role <role-id> --yes
```

Markings restrict who can see a resource: `pltr resource add-markings`,
`remove-markings` and `list-markings`, and
`pltr resource access-requirements` for what a user needs to see it.

## Find and organize resources

```bash
# By path, or by scanning a folder tree (there is no search endpoint)
pltr resource get-by-path "/My Space/My Project/sales"
pltr resource search sales --folder-rid <project-rid> --type dataset --format json > sales.json

# Several resources at once
pltr resource batch-get <resource-rid> <other-resource-rid>

# Copy a folder of datasets elsewhere; check first with --dry-run
pltr cp <folder-rid> <target-folder-rid> --recursive --dry-run
pltr cp <folder-rid> <target-folder-rid> --recursive

# The trash
pltr resource delete <resource-rid> --yes
pltr resource restore <resource-rid>
```

## Review users, groups and audit logs

```bash
pltr admin user list --all --format json > users.json
pltr admin group list --all --format json > groups.json
jq -r '.data[] | [.id, .username] | @tsv' users.json

# An organization's audit log files for a week, then one file
pltr audit list <organization-rid> 2026-11-01 --end-date 2026-11-07 --all --format json > logs.json
pltr audit get <organization-rid> "$(jq -r '.data[0].id' logs.json)" --output audit-1.log
```

## Scripts, CI and agents

```bash
#!/usr/bin/env bash
set -euo pipefail

# Headless authentication: no profile, keyring or configure step
export FOUNDRY_HOST="foundry.company.com"
export FOUNDRY_TOKEN="$CI_FOUNDRY_TOKEN"
export PLTR_FORMAT=json          # every command prints JSON

pltr verify > /dev/null          # exit code 3 if the credentials don't work

# Every page of a list, as one document
pltr folder list <folder-rid> --all > children.json

# Or page by hand with nextPageToken
TOKEN=""
while :; do
  if [ -n "$TOKEN" ]; then
    PAGE=$(pltr admin user list --page-size 500 --page-token "$TOKEN")
  else
    PAGE=$(pltr admin user list --page-size 500)
  fi
  echo "$PAGE" | jq -c '.data[]'
  TOKEN=$(echo "$PAGE" | jq -r '.nextPageToken // empty')
  [ -n "$TOKEN" ] || break
done

# Destructive commands never prompt without a terminal: pass --yes
pltr dataset branches delete <dataset-rid> old-branch --yes
```

When a command fails, its exit code says why (3 authentication, 4 permission
denied, 5 not found, 6 validation, 7 other API or network errors) and, in
JSON mode, the last stderr line is a JSON error with Foundry's `errorName`:

```bash
if ! pltr dataset get <dataset-rid> > dataset.json 2> error.json; then
  jq -r '"\(.type): \(.message)"' < <(tail -n 1 error.json)
fi
```

See the README's
[Output, errors and exit codes](../../README.md#output-errors-and-exit-codes).

## Explore interactively

```bash
pltr shell --profile production
```

```
pltr> admin user current
pltr> ontology list
pltr> sql execute 'SELECT COUNT(*) FROM `<dataset-rid>`'
pltr> help dataset
pltr> exit
```

In the shell, commands run without the `pltr` prefix, with completion and
history; aliases work too.
