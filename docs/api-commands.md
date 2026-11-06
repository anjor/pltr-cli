# `pltr api`: generated commands for the whole Foundry Platform API

`pltr api` has one command for every public method of the Foundry Platform SDK
(`foundry-platform-sdk`, V2 client): 392 commands in 18 namespaces for SDK 1.111.0.
The commands are generated from the SDK, so they mirror it one to one and stay
complete after an SDK upgrade with a regeneration instead of hand work.

They complement the curated commands (`pltr dataset`, `pltr ontology`,
`pltr orchestration`, ...). Curated commands remain the polished path for common
tasks, with friendlier arguments and tables. Reach for `pltr api` when you need
an endpoint the curated commands don't cover, or when you want the API's exact
request and response shapes, for example in scripts and agents.

Every generated command uses pltr's authentication and profiles, prints the SDK's
own JSON with `--format json`, returns documented exit codes, labels beta
endpoints and asks before destructive operations.

## The command tree

```
pltr api <namespace> <resource> [<sub-resource>...] <method> [ARGUMENTS] [OPTIONS]
```

Names come from the SDK client, `FoundryClient.<namespace>.<Resource>[.<SubResource>...].<method>`,
with `snake_case` and `CamelCase` turned into `kebab-case`:

| SDK call | Command |
|---|---|
| `client.admin.User.list()` | `pltr api admin user list` |
| `client.datasets.Dataset.Branch.list(dataset_rid)` | `pltr api datasets dataset branch list DATASET_RID` |
| `client.ontologies.LinkedObject.list_linked_objects(...)` | `pltr api ontologies linked-object list-linked-objects ONTOLOGY OBJECT_TYPE PRIMARY_KEY LINK_TYPE` |
| `client.orchestration.Build.get(build_rid)` | `pltr api orchestration build get BUILD_RID` |

Explore the tree with `--help` at any level:

```bash
pltr api --help                     # namespaces
pltr api datasets --help            # resources of a namespace
pltr api datasets dataset --help    # methods and sub-resources
pltr api datasets dataset get --help
```

A command's help shows the SDK docstring, the endpoint's required scopes, the SDK
method and the HTTP endpoint it calls, so you can look it up in Foundry's API
reference.

## Arguments and options

Positional arguments are exactly the endpoint's path parameters, in order. Most of
them are RIDs (Resource Identifiers such as
`ri.foundry.main.dataset.c26f11c8-cdb3-4f44-9f5d-9816ea1c82da`); `--help` lists each
argument with its SDK type, for example `DATASET_RID ... Type: DatasetRid`.
Everything else is an option named after the SDK parameter (`page_size` becomes
`--page-size`).

| SDK parameter | CLI shape |
|---|---|
| Path parameter | positional argument |
| `str`, RID and ID types | `--name TEXT` |
| `int`, `float` | `--name INTEGER`, `--name FLOAT` |
| `bool` | `--name / --no-name` (leave both out to use the API's default) |
| `Literal[...]` (enums) | `--name [A\|B\|C]` |
| `List[str]`, list of enums | repeatable: `--name a --name b`; leaving out a list the API requires sends `[]` |
| date, date-time | ISO-8601 text: `2026-01-31`, `2026-01-31T12:00:00Z` |
| Models, unions, dicts, lists of models | `--name JSON` (see below) |
| `bytes` request body | `--body FILE`, or `--body -` to read stdin |
| `preview`, `request_timeout` | not exposed (`preview` is automatic, see Beta) |

Optional parameters you leave out are not sent, so the API's defaults apply.
An SDK parameter whose name collides with one of pltr's own options gets an
`--api-` prefix: `pltr api datasets dataset read-table --api-format CSV` passes
the API's `format` parameter (`--format` stays pltr's output format).

For uploads whose API needs the content length (`ontologies attachment upload`),
pltr fills in `--content-length` from the size of `--body` when you leave it out.

### JSON input

Options of type `JSON` take the value in the shape of Foundry's REST API
(camelCase field names, as in Foundry's API docs and in pltr's JSON output):

```bash
pltr api admin user search --where '{"type": "queryString", "value": "jane"}'
pltr api ontologies ontology-object search my-ontology Aircraft --where @query.json --select tailNumber
cat filter.json | pltr api orchestration build search --where @-
```

The value is inline JSON, `@path/to/file.json`, or `@-` for stdin. pltr parses the
JSON and the SDK validates it (unions are resolved by their `type` field). Invalid
JSON, or values the SDK rejects before sending (for example a malformed user ID),
fail with exit code 2 and nothing is sent.

## Output

| Option | Effect |
|---|---|
| `--format table` | default; a table of the result (one row per item for lists) |
| `--format json` | the SDK's own serialization (see below) |
| `--format csv` | CSV with one column per top-level field |
| `PLTR_FORMAT=json` | sets the default format, for agents and CI |
| `--output FILE`, `-o FILE` | write the formatted output to a file instead of stdout |
| `--profile NAME` | authentication profile (default: the active profile) |

stdout carries only data. Messages (such as "more results are available") and
errors go to stderr; in JSON mode stderr carries only the structured error, if any.

JSON output is the SDK's serialization of the response model,
`model_dump(mode="json", by_alias=True, exclude_none=True)`: Foundry API field names
(camelCase), null fields left out, datetimes as ISO-8601 strings, 64-bit integers
(`Long`) as strings, exactly as the SDK sends them. A single object is printed as
that object. An endpoint that returns no content prints `null`.

### Pagination

Paged endpoints (they return an SDK `ResourceIterator`, or a response with a
`nextPageToken`, such as `admin user search`) print one page by default, in the
API's own response shape:

```bash
$ pltr api admin user list --page-size 2 --format json
{
  "data": [
    {"id": "...", "username": "jdoe", ...},
    {"id": "...", "username": "asmith", ...}
  ],
  "nextPageToken": "v1.abc..."
}
```

Pass the token back with `--page-token` to get the next page, or use `--all` to
fetch every page and print `{"data": [...all items...]}`. Page-level fields such as
`totalCount` appear in single-page output only. In table and CSV mode the next
page token is printed on stderr.

### Binary responses

Commands that return file content (`datasets dataset file content`,
`media-sets media-set read`, `sql-queries sql-query get-results`, ...) stream the
bytes to `--output-file FILE`, or to stdout when stdout is not a terminal:

```bash
pltr api datasets dataset file content "$DATASET_RID" data/flights.csv --output-file flights.csv
pltr api datasets dataset file content "$DATASET_RID" data/flights.csv > flights.csv
```

pltr refuses to write binary data to a terminal (exit code 2); a failed download
leaves no partial file behind. Arrow and Parquet results
(`datasets dataset read-table`, `sql-queries sql-query get-results`) are written as
the raw bytes the API returns.

## Beta endpoints

About half of the SDK's methods are beta (their SDK signature has a `preview`
parameter). Their commands are labeled `[beta]` at the start of their help and in
command lists, and pltr calls them with `preview=True` automatically; there is no
flag to pass.

The check happens at run time against the installed SDK: when a newer SDK has
promoted a method to GA, pltr stops passing `preview`, so the command neither warns
nor fails.

## Destructive operations

Commands that delete, remove, revoke, replace, reset, clear, cancel, abort,
disable or undeploy something, or overwrite data, ask for confirmation on stderr
before calling the API. `--yes` (`-y`) skips the question. When stdin is not a
terminal pltr never prompts: without `--yes` the command fails with exit code 2
and sends nothing.

```bash
pltr api admin user delete "$USER_ID"          # asks first
pltr api admin user delete "$USER_ID" --yes    # for scripts and agents
```

The list is explicit and reviewed (`V2_DESTRUCTIVE` in
`scripts/generate_api_commands.py`). It holds every method named `delete`,
`permanently_delete`, `remove*`, `revoke*`, `replace*`, `abort`, `cancel` or
`disable`, plus methods whose names don't say so: `connectivity connection
update-secrets`, `datasets dataset put-schema`, `media-sets media-set clear`,
`streams dataset stream reset`, `streams dataset stream subscriber reset-offsets`
and `third-party-applications third-party-application website undeploy`.

## Errors and exit codes

| Exit code | Meaning |
|---|---|
| 0 | success |
| 1 | unexpected error, "no" at a confirmation prompt, or an SDK method missing from the installed SDK |
| 2 | usage error: bad or missing arguments, invalid JSON input, a value the SDK rejects, a destructive command without `--yes` and no terminal |
| 3 | authentication: no usable profile or credentials, HTTP 401 |
| 4 | permission denied (HTTP 403) |
| 5 | not found (HTTP 404) |
| 6 | the API rejected the request (HTTP 400, 422) |
| 7 | other API or network errors (409, 413, 429, 5xx, timeouts, connection errors) |

With `--format json` (or `PLTR_FORMAT=json`) a failure writes one compact JSON
object to stderr, including the Foundry error name and parameters for API errors:

```json
{"type":"not_found","message":"UserNotFound: The given User could not be found.","exitCode":5,"statusCode":404,"errorName":"UserNotFound","errorInstanceId":"...","parameters":{"userId":"..."}}
```

## Methods without a command

Two SDK methods stream server-sent events, which a command printing one JSON
document can't represent yet: `functions.Query.streaming_execute` and
`functions.Query.streaming_execute_events`. Use `pltr api functions query execute`
instead. `uv run python scripts/coverage.py` lists every method, its command and
the exclusions with their reasons.

## SDK versions

pltr's `pyproject.toml` allows a range of SDK versions, while the commands are
generated from the version in `uv.lock`. Each command looks up its SDK method by
name when it runs. If the installed SDK no longer has the method or one of the
parameters you passed, the command fails with exit code 1 and a message naming the
installed and the generated SDK versions. Installing pltr in its own environment
keeps the SDK at the version pltr was tested with:

```bash
uv tool install pltr-cli    # or: pipx install pltr-cli
```

## For maintainers

### Regenerating after an SDK bump

1. Bump `foundry-platform-sdk` (`uv lock --upgrade-package foundry-platform-sdk`,
   then `uv sync`).
2. Run `uv run python scripts/generate_api_commands.py`. It stops with an
   explanation when a new method needs a decision:
   - a method whose name looks destructive (`delete`, `remove*`, ...) must be added
     to `V2_DESTRUCTIVE`, or to `not_destructive` if it isn't;
   - a server-sent-events method must be added to `excluded` with a reason;
   - a configured method that no longer exists must be removed from the config.
3. Review the diff of `src/pltr/commands/api/_specs/`: new and removed commands,
   `beta` changes, new parameters. Read the names of new methods: if one destroys
   or overwrites data without saying so, add it to `V2_DESTRUCTIVE` and regenerate.
4. Run `uv run python scripts/coverage.py` and `uv run pytest tests/test_api_commands`.

`tests/test_api_commands/test_generator.py` regenerates the specs in memory and
fails when the committed files differ, so CI catches a forgotten regeneration. The
output is byte-identical on Python 3.10 to 3.13 and on every OS.

### How it fits together

- `scripts/generate_api_commands.py` walks the SDK client with `inspect`: namespaces
  are the client's `*Client` attributes, resources and sub-resources are
  `cached_property` attributes, methods are the public functions of each resource
  client. For each method it reads the signature, the docstring and the
  `core.RequestInfo(...)` call in the method body (HTTP method, path, and whether
  each parameter is sent in the path, query, headers or body).
- It writes one spec module per namespace to `src/pltr/commands/api/_specs/`
  (plain Python literals, `# fmt: off`), plus `_specs/__init__.py`, a small index of
  namespaces with the SDK version.
- `src/pltr/commands/api/_runtime.py` builds click groups and commands from the
  specs. Nothing is imported until it is needed: `pltr --help` doesn't load any
  spec, `pltr api --help` reads only the index, and `pltr api datasets ...` loads only
  the datasets spec.
- `src/pltr/commands/api/_adapter.py` holds output formatting, error mapping, exit
  codes and confirmation for the generated commands.

A method spec looks like this (keys left out when they don't apply):

```python
{
    "name": "list",                 # CLI name
    "sdk": "list",                  # SDK attribute
    "summary": "Lists all Users.",  # short help
    "help": "Lists all Users.\n\nThis is a paged endpoint...",
    "http": "GET /v2/admin/users",
    "beta": True,                   # has a `preview` parameter
    "paged": "iterator",            # or "response"
    "binary": True,                 # bytes response
    "destructive": True,            # asks for confirmation
    "params": [
        {"name": "include", "in": "query", "api": "include", "type": "choice", "choices": ["ACTIVE", "DELETED"]},
        {"name": "page_size", "in": "query", "api": "pageSize", "type": "int", "help": "..."},
    ],
}
```

Parameter `type` is one of `str`, `int`, `float`, `bool`, `choice`, `date`,
`datetime`, `json` and `bytes`; `multiple`, `required`, `schema` (the SDK type
name), `option` (a renamed option) and `auto` (a computed default) are added when
they apply. `in` is where the API takes the parameter (`path`, `query`, `header`
or `body`) and `api` its API name. `required` is the SDK's: the runtime makes
required repeatable options optional on the command line and sends `[]` when they
are left out.

### Adding the V3 API

V3 (`foundry_sdk.v3`) is a separate client. Generating it is a configuration
change: add an `ApiVersionConfig` to `API_VERSIONS` in the generator, for example
`key="v3"`, `client="foundry_sdk.v3:FoundryClient"`, `cli_group="v3"` (commands
under `pltr api v3 ...`) and `module_prefix="v3_"`, with its own destructive and
exclusion lists. The runtime then needs a client factory for `"v3"` in
`_runtime.get_client`.
