# Pagination Guide

Commands that list things fetch **one page** by default. This guide covers
the paging options, the JSON shape of a page, and the commands that page in
their own way.

## Options

Every paged command takes the same four options:

| Option | Effect |
|---|---|
| `--page-size N` | Items per page. Without it, the API's default page size is used. |
| `--page-token TOKEN` | Start from the page a previous response's `nextPageToken` points to. |
| `--max-pages N` | Fetch up to N pages (default 1). |
| `--all` | Fetch every page (overrides `--max-pages`). |

```bash
# The first page
pltr admin user list

# Every page
pltr admin user list --all

# Up to 5 pages of 100
pltr dataset files list <dataset-rid> --page-size 100 --max-pages 5

# Continue where an earlier call stopped
pltr admin user list --page-size 100 --page-token <token>
```

`--all` reads everything into memory before printing, so prefer
`--page-size` with `--page-token` for very large lists.

## Output

With `--format json`, a paged command prints one JSON document in the API's
paged shape:

```json
{
  "data": [
    {"id": "...", "username": "jane.doe", ...},
    {"id": "...", "username": "john.roe", ...}
  ],
  "nextPageToken": "v1.abc..."
}
```

`nextPageToken` is there only when more pages exist; pass it to
`--page-token` to continue. With `--max-pages` or `--all`, `data` holds the
items of every page fetched, and `nextPageToken` says where to resume.

In table and CSV output each item is one row. When more pages exist, a hint
goes to stderr:

```
More results available. Next page: --page-token v1.abc... (or --all to fetch every page).
```

A script can page by hand:

```bash
TOKEN=""
while :; do
  if [ -n "$TOKEN" ]; then
    PAGE=$(pltr admin user list --page-size 500 --format json --page-token "$TOKEN")
  else
    PAGE=$(pltr admin user list --page-size 500 --format json)
  fi
  echo "$PAGE" | jq -c '.data[]'
  TOKEN=$(echo "$PAGE" | jq -r '.nextPageToken // empty')
  [ -n "$TOKEN" ] || break
done
```

## Paged Commands

- **dataset**: `branches list`, `branches transactions`, `files list`,
  `transactions list`, `schedules list`, `jobs list`
- **filesystem**: `folder list`, `space list`, `project list`,
  `project list-orgs`, `resource list`, `resource list-markings`,
  `resource-role list`
- **ontology**: `object-type-list`, `object-list`, `object-search`,
  `object-linked`
- **orchestration**: `builds jobs`, `builds search`, `schedules runs`
- **connectivity**: `import list-file`, `import list-table`
- **admin**: `user list`, `user search`, `group list`, `group search`,
  `marking list`
- **others**: `aip-agents sessions list`, `aip-agents versions list`,
  `models version list`, `audit list`, `widgets release list`

Every paged `pltr api` command takes the same options; see
[`pltr api`](api-commands.md#pagination).

## Commands That Page Differently

- `ontology object-search` prints the API's response, which also has a
  `totalCount`.
- `project list` without `--space-rid` lists the projects of every space and
  reads every page, so it rejects `--page-token` and `--max-pages`.
- `resource list --type` and `resource-role list --principal-type` filter
  each page locally (the API has no such filter), so a page can have fewer
  items than `--page-size`.
- `audit list` without `--end-date` has no end: the API returns a
  `nextPageToken` on every page so that you can poll for new log files.
  Paging stops at the first empty page, and its `nextPageToken` picks up
  later files.
- `resource search` isn't paged: it scans folders and stops after
  `--limit` matches or `--max-folders` folders, printing `{"data": [...]}`.
- `admin org available-roles` isn't paged: the API returns every role at
  once.
- A paged `pltr api` command without `--max-pages` or `--all` prints the
  page exactly as the API returns it, page-level fields included.

## Changes From Earlier Releases

See the [pagination migration guide](migration/v2-pagination.md).
