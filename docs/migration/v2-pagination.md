# Migration Guide: Pagination

How list commands changed, and how to update scripts that use them. For
every change in a release, see [CHANGELOG.md](../../CHANGELOG.md).

## In the Next Release (Unreleased)

### Every list command fetches one page by default

Commands that used to read every page now read one, like the rest:
`folder list`, `space list`, `project list --space-rid`,
`project list-orgs`, `resource list`, `resource list-markings`,
`resource-role list`, `ontology object-linked`, `audit list`,
`widgets release list`, and the paged `dataset` commands such as
`branches list` and `transactions list`. Add `--all` where a script needs
everything:

```bash
# Before: every child of the folder
pltr folder list <folder-rid> --format json

# Now
pltr folder list <folder-rid> --format json --all
```

### The page size is the API's default

Without `--page-size`, commands use the API's default page size; they used
to send pltr's `page_size` setting (20 by default). Pass `--page-size`
where you depend on a size.

### JSON lists have the API's paged shape

`--format json` prints `{"data": [...], "nextPageToken": "..."}`, with the
items in the API's own field names (camelCase). Commands used to print a
bare list, or `{"data": [...], "pagination": {...}}` with snake_case keys.

```bash
# Before
pltr admin user list --format json | jq '.data | length'
pltr admin user list --format json | jq -r '.pagination.next_page_token'
pltr ontology object-type-list <ontology> --format json | jq '.[].api_name'

# Now
pltr admin user list --format json | jq '.data | length'
pltr admin user list --format json | jq -r '.nextPageToken // empty'
pltr ontology object-type-list <ontology> --format json | jq -r '.data[].apiName'
```

`nextPageToken` is left out on the last page. The "next page" hint of table
and CSV output goes to stderr, so stdout stays parseable.

## In 0.12.0

0.12.0 added `--page-size`, `--page-token`, `--max-pages` and `--all` to
`admin user list`, `orchestration builds search`, `ontology object-list`
and `dataset files list`, and these commands started to fetch one page by
default. Add `--all` to get every page, as before.

`orchestration builds search` now also needs a filter, such as `--status`
or `--branch`:

```bash
pltr orchestration builds search --status FAILED --all --format json
```
