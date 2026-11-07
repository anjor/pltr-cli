# Workflow: find and explore data

Find a resource's RID, look inside datasets, query them with SQL and read
ontology objects. Every command here prints one JSON document with
`--format json` (or `PLTR_FORMAT=json`); see SKILL.md for the output rules.

## 1. Find the RID

Foundry addresses resources by RID. If the user gives a path or a name,
resolve it first:

```bash
# A path you know (the leading slash is optional)
pltr resource get-by-path "/My Space/My Project/flights" --format json

# A name you don't know the folder of: scan below a folder (one request per folder)
pltr resource search flights --folder-rid ri.compass.main.folder.<id> --type dataset --format json

# Browse: spaces, then projects, then folders (the root folder is ri.compass.main.folder.0)
pltr space list --format json
pltr project list --format json
pltr folder list ri.compass.main.folder.<id> --format json --all
```

`resource search` lists folders one by one, so start it from the narrowest
folder you know.

## 2. Look inside a dataset

```bash
DATASET=ri.foundry.main.dataset.<id>

pltr dataset get "$DATASET" --format json
pltr dataset schema get "$DATASET" --format json
pltr dataset branches list "$DATASET" --format json
pltr dataset files list "$DATASET" --format json

# Download one file (binary-safe: the content goes to the file)
pltr dataset files get "$DATASET" data/part-00000.csv ./part-00000.csv

# The first rows as a table
pltr dataset preview "$DATASET" --limit 20

# The whole table as CSV, straight from the API
pltr api datasets dataset read-table "$DATASET" --api-format CSV --row-limit 1000 --output flights.csv
```

## 3. Query with SQL

SQL uses Spark SQL. Refer to a dataset by its RID (or path) in backticks:

```bash
pltr sql execute 'SELECT origin, COUNT(*) AS flights FROM `ri.foundry.main.dataset.<id>` GROUP BY origin ORDER BY flights DESC LIMIT 20' --format json
```

For long queries, submit and poll instead of waiting on one call:

```bash
pltr sql submit 'SELECT * FROM `ri.foundry.main.dataset.<id>`'   # note the query ID it prints
pltr sql status <query-id>
pltr sql results <query-id> --format csv --output results.csv
```

## 4. Read ontology objects

Ontologies are addressed by RID or API name; object types and properties by
API name.

```bash
pltr ontology list --format json
pltr ontology object-type-list ri.ontology.main.ontology.<id> --format json
pltr ontology object-get ri.ontology.main.ontology.<id> Aircraft N123AB --format json
pltr ontology object-count ri.ontology.main.ontology.<id> Aircraft --format json

# Typed search (Foundry's SearchJsonQueryV2), one page at a time
pltr ontology object-search ri.ontology.main.ontology.<id> Aircraft \
  --where '{"type": "and", "value": [{"type": "eq", "field": "status", "value": "ACTIVE"}, {"type": "gt", "field": "seats", "value": 100}]}' \
  --properties tailNumber,seats --page-size 100 --format json

# The same endpoint with the API's exact request options
pltr api ontologies ontology-object search ri.ontology.main.ontology.<id> Aircraft \
  --where '{"type": "eq", "field": "status", "value": "ACTIVE"}' \
  --select tailNumber --snapshot --format json
```

Pass the response's `nextPageToken` to `--page-token` for the next page.
Applying actions changes data: `pltr api ontologies action apply` takes the
action's parameters as JSON (`--parameters`); confirm the action and its
parameters with the user first.
