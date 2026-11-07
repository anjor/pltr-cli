### Breaking

- **`ontology` commands: `--format json` prints the SDK's own serialization**
  (Foundry API field names in camelCase, null fields left out, nothing
  invented):
  - `ontology list` prints the API response, `{"data": [<OntologyV2>...]}`
    (was a list of `rid`/`api_name`/`display_name`/`description` dicts).
  - `ontology get` and `object-type-get` print the `OntologyV2` /
    `ObjectTypeV2` model (were snake_case subsets).
  - `object-type-list`, `object-list` and `object-linked` print
    `{"data": [...], "nextPageToken": "..."}`. `object-list` used to print
    `{"data": [...], "pagination": {"page", "items_count", "has_more",
    "total_pages_fetched", "next_page_token"}}`; `object-type-list` and
    `object-linked` printed bare lists.
  - `object-search` prints the API response
    `{"data": [...], "nextPageToken": "...", "totalCount": "N"}` (pages
    merged; `totalCount` is a Foundry Long, a string in JSON).
  - `object-aggregate` prints the API response
    `{"accuracy": ..., "data": [{"group": {...}, "metrics": [{"name", "value"}]}]}`.
  - `object-count` prints `{"count": N}`.
  - `action-apply` and `action-validate` print the API response
    `{"operationId", "validation", "edits"}`. The old output read fields the
    response doesn't have (`rid`, `status`, `created_objects`, ...,
    `valid`, `errors`, `warnings`) and was always null/empty.
  - `query-execute` prints the API response, `{"value": <the result>}` (it
    printed `{"result": "<Python repr>"}` because it read fields the response
    doesn't have).
  - `object-type-create` and `link-type-create` print the response body as
    Foundry returns it, or `null` when it is empty; pltr no longer adds
    `apiName` and `ontologyRid` to it.
- **Status messages go to stderr**, and errors are structured, with the
  documented exit codes (2 usage, 3 credentials, 4 permission denied, 5 not
  found, 6 validation, 7 other API/network errors) instead of 1 for every
  error.
- **`ontology object-search`: `--query/-q` is removed.** The Foundry search
  API has no free-text search; it filters properties with a typed query.
  Use `--where` (see Added). `--query` is kept hidden for one release and
  fails with a usage error that suggests the equivalent `--where`
  (`containsAnyTerm` on a property). The command never worked before.
- **`ontology object-aggregate` takes the aggregations from
  `--aggregation`.** The `AGGREGATIONS` argument is a hidden, deprecated
  alias for one release (it warns). Both take the Foundry API's aggregation
  objects (`[{"type": "count"}, {"type": "avg", "field": "salary"}]`); the
  shape the docs showed (`{"count": "count", "avg_salary": "avg"}`) never
  worked and is rejected with a usage error. `--filter` is a hidden,
  deprecated alias of `--where` for one release. The command never worked
  before.
- **`ontology object-linked` fetches one page by default**; it used to fetch
  every page. Use `--all`, `--max-pages N` or `--page-token`.
- **`ontology object-list` uses the API's default page size** unless
  `--page-size` is given; it used to default to the `page_size` setting
  (20). Like every paged command, it fetches one page by default.
- **`ontology action-apply` fails with exit code 6 when Foundry reports the
  parameters INVALID** (nothing was applied), instead of printing a result.
- **Table and CSV columns changed** to read real model fields: ontologies
  (API Name, Display Name, RID, Description), object types (status, primary
  key, title property, properties with their types, datasources), action
  results (operation ID, validation result, edits summary), validation
  results (result, submission criteria, per-parameter results), aggregations
  (one row per group: a column per group value and per metric), queries (one
  row per item of a list result). Objects keep one column per property.
- **`--format` is validated**: only table, json and csv are accepted
  (case-insensitive); the default comes from `PLTR_FORMAT`.

### Added

- `ontology action-apply-batch ONTOLOGY ACTION REQUESTS`: apply several
  actions of one action type in one request (`Action.apply_batch`).
  `REQUESTS` is the API's list of `{"parameters": {...}}` objects. Options:
  `--return-edits ALL|NONE`, `--scenario-rid`. Not confirmed, like
  `action-apply`.
- `ontology object-search --where JSON`: the Foundry API's search query
  (`SearchJsonQueryV2`), inline or `@file.json`, e.g.
  `{"type": "eq", "field": "department", "value": "Engineering"}`. Also
  `--order-by JSON` (`SearchOrderByV2`), `--default-load-level`,
  `--derived-properties/--no-derived-properties`, `--page-token`,
  `--max-pages` and `--all`.
- `ontology object-aggregate --aggregation JSON`, `--where JSON`,
  `--accuracy REQUIRE_ACCURATE|ALLOW_APPROXIMATE` and `--branch`.
  `--group-by` takes the API's group-by objects as JSON
  (`[{"type": "fixedWidth", "field": "salary", "fixedWidth": 10000}]`), or
  comma-separated property names as shorthand for exact groupings.
- JSON inputs (`--where`, `--aggregation`, `--group-by`, `--order-by`, batch
  `REQUESTS`) are validated with the SDK's own models before anything is
  sent: a mistake is a usage error (exit 2) that names the location and the
  problem (for example `at value[1].value (type 'gt'): required field
  missing`, or an unknown `type` with the list of valid ones). Fields the
  SDK models don't know are sent as is, with a warning.
- `ontology object-get --scenario-rid`, `--transaction-id`,
  `--derived-properties/--no-derived-properties` and `--branch/-b`.
- `ontology object-list` and `object-linked`: `--branch/-b` and
  `--derived-properties/--no-derived-properties`; `object-linked` also
  `--page-token`, `--max-pages` and `--all`.
- `ontology object-type-list` and `object-type-get`: `--include-datasources`;
  `object-type-list` also `--page-size`, `--page-token`, `--max-pages` and
  `--all`.
- `ontology action-apply --return-edits ALL|ALL_V2_WITH_DELETIONS|NONE`,
  `--attribution` and `--scenario-rid`.
- Action and query parameters (`PARAMETERS`, `--parameters`) accept
  `@file.json`.
- `[beta]` label on `ontology object-count`, which calls a beta endpoint
  (always with `preview=true`).
- The ontology argument of the read, action and query commands accepts the
  ontology's API name as well as its RID (the help now says so).

### Fixed

- `ontology action-apply` passes `parameters` by keyword (#182).
- `ontology action-validate` validates through `Action.apply` in
  `VALIDATE_ONLY` mode (the SDK has no `Action.validate`), and exits 0 with
  the validation result whether it is VALID or INVALID (#182).
- `ontology object-aggregate` sends `aggregation`, `groupBy` and `where`
  (#182).
- `ontology object-search` filters with `where`, always sends `select`
  (empty: every property), reads the response's `data` and pages with its
  `nextPageToken` (#182).
- `ontology object-count` calls the beta endpoint with `preview=true` and
  prints the count (#182).
- Output of `action-apply`, `action-validate`, `object-count` and
  `query-execute` reads the response models' real fields (#183).
- `object-type-create` / `link-type-create` errors keep the HTTP status and
  Foundry error body (a 403 exits 4, a 400 exits 6, no schema endpoint on
  the stack exits 5); a non-JSON success response is an API error (exit 7).

### Removed

- Internal: `ObjectTypeService.list_outgoing_link_types` (unused; the
  generated `pltr api ontologies ontology object-type
  list-outgoing-link-types` covers it), `OntologyObjectService.list_objects_paginated`
  and the `_format_*` helpers of the ontology services, and the client-side
  20-request cap of the (previously unused) batch apply: Foundry enforces
  its own limit, which is higher for some actions.

### Docs to update

- `docs/user-guide/commands.md` (lines 964-1025) and
  `claude_skill/reference/ontology-commands.md` (lines 76-128, 160):
  `object-aggregate ONTOLOGY_RID OBJECT_TYPE AGGREGATIONS` with
  `'{"count": "count"}'` never worked. Use
  `pltr ontology object-aggregate <ONTOLOGY> Employee --aggregation '[{"type": "count", "name": "employees"}]' --group-by department`.
  Document `object-search --where` (no `--query`), `object-count` ([beta]),
  `action-apply-batch`, the new options above, and that the ontology
  argument is an API name or RID.
- `claude_skill/reference/ontology-commands.md` line 11: `ontology list` has
  no `--page-size`.
- `docs/examples/gallery.md` (lines 273, 315, 548) and
  `docs/user-guide/workflows.md` (line 84),
  `claude_skill/workflows/data-analysis.md` (line 102): aggregation examples
  use the never-working `'{"count": "count", "avg_tenure": "avg"}'` argument;
  rewrite with `--aggregation '[{"type": "count", "name": "count"}, {"type": "avg", "field": "tenure", "name": "avgTenure"}]'`.
- `docs/pagination.md` (lines 63, 127-142, 322-355, 413):
  `ontology object-list` JSON is now `{"data": [...], "nextPageToken": ...}`
  (no `pagination` block), and its default page size is the API's.
- `docs/user-guide/troubleshooting.md` (line 274): `action-apply` also
  accepts `@params.json`.
- README "Output, errors and exit codes": the ontology commands follow the
  contract now.

### Not verified live

- The schema endpoints of `object-type-create` / `link-type-create` are
  unchanged and still unverified (#143 calls them undocumented internal
  APIs). The first two, `/v2/ontologies/{ontology}/objectTypes` and
  `/v1/...`, are requested at the host root, not under `/api` where
  Foundry's public API lives, so on a real stack they probably return 404
  (and pltr falls through to the next endpoint). If one returns an HTML
  page with status 200 instead, pltr now reports an API error (exit 7)
  rather than a parse failure; it doesn't fall through.
- `object-search` sends `select: []` when `--properties` isn't given;
  assumed (Foundry convention) to return every property.
- `action-apply` treats a 200 response whose `validation.result` is INVALID
  as "not applied" (exit 6), per the SDK docstring ("a 200 HTTP status code
  only indicates that the request was received"); Foundry may instead always
  answer such requests with a 400 `ActionValidationFailed`, which also exits
  6.
- `object-count` with `preview=true` (#178 confirmed it fails without it).
- `--return-edits` output, the `attribution` header, `--default-load-level`,
  `--derived-properties`, `--scenario-rid`, `--transaction-id` and
  `--include-datasources` are sent as the SDK defines them; their effect on
  real responses wasn't checked.
- The meaning of `excludedItems` in aggregate responses (pltr only reports
  the number).
