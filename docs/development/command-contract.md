# The command contract: writing a command

Every curated command and every generated `pltr api` command talks to the user
through one shared layer, `pltr.contract`. This guide is the checklist for
adding a command or a command module, and for changing one. Every module
follows it; `pltr folder` and `pltr space` (`src/pltr/commands/{folder,space}.py`,
`src/pltr/services/{folder,space}.py` and their tests) are the reference
implementations: copy their shape.

Import everything from `pltr.contract` and nothing from its submodules.

## The contract (what users and agents rely on)

1. **stdout is data only, in every format.** Spinners, progress, success,
   info and warning messages, prompts and errors go to stderr.
2. **`--format json` prints the SDK's own serialization**, exactly one JSON
   document: `model.model_dump(mode="json", by_alias=True, exclude_none=True)`.
   That means Foundry API field names (camelCase), no null fields and no
   invented fields. Lists use the API's paged shape
   `{"data": [...], "nextPageToken": "..."}`, with `nextPageToken` left out
   on the last page. A single object is printed as that object. A call with
   no response body prints `null`.
3. **In JSON mode stderr carries JSON Lines only.** Informational messages
   are suppressed, and warnings are `{"type": "warning", "message": ...}`.
   On failure the last line is the structured error (see
   [Errors](#errors-and-exit-codes)).
4. **Table and CSV output use curated columns**, and every column reads a
   field that really exists on the SDK model. A missing field fails a test.
5. **Exit codes are documented** (see the table below).
6. **Destructive commands confirm**, and `--yes`/`-y` skips the prompt.
   Nothing ever prompts when stdin is not a terminal: without `--yes` the
   command fails with exit code 2.
7. **Beta endpoints** are always called with a literal `preview=True`, and
   the command's help starts with `[beta]`. GA endpoints never get `preview`.
8. The default format is `table`. `PLTR_FORMAT=json|csv|table` changes it.

## Checklist for a command module

1. **Service** (`src/pltr/services/<module>.py`):
   - Return SDK models, SDK iterators or responses unchanged. Delete the
     `_format_*`/`_serialize_*` dict helpers and every
     `getattr(obj, "field", default)`.
   - Don't catch SDK exceptions. If you must add context, use
     `raise SomeError("context") from e`, so the error layer finds the SDK
     exception through `__cause__`.
   - GA methods get no `preview`. Beta methods get a literal `preview=True`.
     A method is beta if its signature has a `preview` parameter; check with
     `inspect.signature` against the installed SDK.
2. **Command** (`src/pltr/commands/<module>.py`), for each command:
   - Add `@pltr_command(sdk=..., beta=..., destructive=..., paged=...)`
     directly under `@app.command(...)`.
   - Declare the shared options: `ProfileOption`, `FormatOption`,
     `OutputOption`, plus `YesOption` for destructive commands and the paging
     options for paged commands.
   - Print data with `emit(...)` only. Use `success`, `info`, `warn` and
     `spinner` for everything else.
   - Delete the `try/except ... raise typer.Exit(1)` blocks. The decorator
     handles errors.
   - Validate input with `raise typer.BadParameter(...)`.
   - For a destructive command, call `confirm_destructive(...)` before the
     API call.
   - Put the help text in the docstring, not in `help=`, so beta commands get
     their `[beta]` label.
   - Don't create a `Console()` or call `console.print(...)`: print through
     `pltr.contract`.
3. **Flags:** keep existing flag names. When a flag is renamed or removed,
   keep the old one as a hidden alias for one release. Use
   `ConfirmAliasOption`/`ForceAliasOption` for `--confirm`/`--force` that
   meant "skip confirmation", and `PreviewNoopOption` for `--preview`.
4. **Tests:** rewrite the module's command and service tests against
   `stub_foundry_http` (see [Tests](#tests)).
5. **Contract-test cases:** in `tests/test_contract/cases/<module>.py`, delete
   the command from `NOT_CONVERTED` and add its `SUCCESS` case (see
   [The contract test](#the-contract-test)).
6. **Changelog:** add your entries under `## [Unreleased]` in
   `CHANGELOG.md` (see [Changelog](#changelog)).
7. **Agent skill:** when you add or change a command (its help, options or
   metadata), run `uv run python scripts/generate_skill_reference.py` and
   commit `claude_skill/reference/`. A test fails while the reference is
   stale.

## Before and after: `pltr folder get`

Before (abridged):

```python
# commands/folder.py
@app.command("get")
def get_folder(
    folder_rid: str = typer.Argument(..., help="Folder Resource Identifier", ...),
    profile: Optional[str] = typer.Option(None, "--profile", ...),
    format: str = typer.Option("table", "--format", "-f", ...),
    output: Optional[str] = typer.Option(None, "--output", "-o", ...),
):
    """Get detailed information about a specific folder."""
    try:
        cache_rid(folder_rid)
        service = FolderService(profile=profile)
        with SpinnerProgressTracker().track_spinner(f"Fetching folder {folder_rid}..."):
            folder = service.get_folder(folder_rid)
        if format == "json":
            if output:
                formatter.save_to_file(folder, output, "json")
            else:
                formatter.format_dict(folder, format=format)
        elif format == "csv":
            ...
        else:
            _format_folder_table(folder)   # reads folder.get("created") -> always "N/A"
        if output:
            formatter.print_success(f"Folder information saved to {output}")
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get folder: {e}")
        raise typer.Exit(1)

# services/folder.py
def get_folder(self, folder_rid):
    try:
        folder = self.service.Folder.get(folder_rid, preview=True)  # GA: warns
        return self._format_folder_info(folder)  # snake_case dict, invented "type"
    except Exception as e:
        raise RuntimeError(f"Failed to get folder {folder_rid}: {e}")
```

After:

```python
# commands/folder.py
FOLDER_COLUMNS: Columns = {
    "RID": "rid",
    "Display Name": "display_name",
    "Path": "path",
    "Created": "created_time",
    "Created By": "created_by",
    # ...
}

@app.command("get")
@pltr_command(sdk="filesystem.Folder.get")
def get_folder(
    folder_rid: FolderRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a folder's metadata."""
    with spinner(f"Fetching folder {folder_rid}..."):
        folder = FolderService(profile=profile).get_folder(folder_rid)
    cache_rid(folder_rid)
    emit(folder, format=format, output=output, columns=FOLDER_COLUMNS, title="Folder")

# services/folder.py
def get_folder(self, folder_rid: str) -> Any:
    """Get a folder (``Folder.get``, GA); returns a ``Folder`` model."""
    return self.service.Folder.get(folder_rid)
```

## Options

| Annotated type | Flags | Python default |
|---|---|---|
| `ProfileOption` | `--profile/-p` | `None` |
| `FormatOption` | `--format/-f table\|json\|csv`, env `PLTR_FORMAT`, eager | `"table"` |
| `OutputOption` | `--output/-o FILE` | `None` |
| `YesOption` | `--yes/-y` | `False` |
| `ConfirmAliasOption` | hidden `--confirm`, a deprecated alias of `--yes` that warns | `False` |
| `ForceAliasOption` | hidden `--force`, a deprecated alias of `--yes` that warns | `False` |
| `PreviewNoopOption` | hidden `--preview`, a deprecated no-op that warns | `False` |
| `PageSizeOption` | `--page-size N` | `None` |
| `PageTokenOption` | `--page-token TOKEN` | `None` |
| `MaxPagesOption` | `--max-pages N` | `1` |
| `AllPagesOption` | `--all` | `False` |

- Use the exact defaults in the table, for example
  `format: FormatOption = "table"`. The parameter names are up to you, but
  `profile`, `format`, `output`, `yes`, `page_size`, `page_token`,
  `max_pages` and `all_pages` keep modules uniform.
- **Short-flag conflicts.** If a command already uses `-p`, `-f` or `-o` for
  something else (for example `folder create --parent-folder/-p`,
  `project add-orgs --org/-o`, `models model create --folder/-f`), declare
  that one shared option with the factory and `short=False`:
  `profile: Annotated[Optional[str], profile_option(short=False)] = None`.
  The factories are `format_option` and `output_option` too. The contract
  test fails if a command declares an option string twice.
- **Aliases.** Declaring `ConfirmAliasOption`/`ForceAliasOption` is enough:
  `confirm_destructive` honours them through the click context, so the
  parameter can stay unused. Only use `ForceAliasOption` where `--force`
  meant "skip the confirmation prompt".
- **Click commands** (generated code) use the decorators
  `click_profile_option`, `click_format_option`, `click_output_option`,
  `click_yes_option` and `click_page_options`. They take the parameters
  `profile`, `format`, `output`, `yes`, `page_size`, `page_token`,
  `max_pages` and `all_pages`.

## Output: `emit` and columns

```python
emit(result, *, format, output=None, columns=None, rows=None, title=None)
```

- `result` is whatever the SDK returned: a model, a dict, a list, a `Page`,
  an SDK `ResourceIterator` (its current page), a paged response model, or
  `None`. A paged response model (a model with a list `data` and a
  `next_page_token`, such as `ListObjectsResponseV2`) prints in full in JSON
  (with fields such as `totalCount`), and as one row per item of its `data`
  in table and CSV, with the next-page hint.
- **JSON** prints `to_document(result)`. Columns are ignored.
- **Table**: a single object is shown as a vertical Property/Value table, and
  a list as one row per item. An empty list prints `No results.` on stderr.
  When more pages exist, the next `--page-token` hint goes to stderr.
- **CSV** has a header row from the column headers and one row per item. An
  empty list prints only the header.
- **`output=`** writes the rendered text to a file instead of stdout. In
  text mode, a "Wrote ... to FILE" message goes to stderr. `-` means
  stdout, as for binary output.
- **`rows=`** sets the table/CSV rows when they aren't `result` itself, for
  example a batch response whose `data` is a dict:
  `rows=lambda r: list(r.data.values())`. JSON still prints the whole
  response.
- **`Columns`** is an ordered `{header: spec}` mapping. A spec is either:
  - a dotted path, using python field names or API aliases (`"created_time"`,
    `"createdBy"`, `"reference.media_set_view_item.media_set_rid"`), or
  - a callable taking the row item (`lambda s: ", ".join(s.organizations)`).

  On SDK models every path segment must be a declared field, or
  `ColumnError` is raised: a schema mismatch fails your test instead of
  printing `unknown`. A field that exists but is `None` renders empty. On
  plain dicts (ontology objects, raw JSON) a missing key renders empty,
  because the API leaves null fields out. Cells render `None` as empty,
  datetimes as ISO-8601 UTC (as the SDK serializes them), booleans as
  `true`/`false` and nested values as compact JSON. Don't use
  `getattr(model, "x", default)` in a callable.
- Without `columns`, `auto_columns` uses every set model field, named by its
  API name. That suits generated commands; curated commands should declare
  columns.
- **Tabular results** (a `pyarrow.Table`, such as an SQL query result or
  dataset rows read as Arrow): `columns, rows = table_rows(table)` gives one
  dict per row in the table's column order, binary values (also nested)
  base64-encoded and duplicate column names suffixed `_2`, `_3` (with a
  warning); then `emit(rows, format=format, output=output, columns=columns)`.

**Paging.** A paged command has `paged=True`, the four paging options and:

```python
page = collect_pages(
    lambda token: service.list_children(folder_rid, page_size=page_size, page_token=token),
    page_token=page_token, max_pages=max_pages, all_pages=all_pages,
)
emit(page, format=format, output=output, columns=CHILD_COLUMNS)
```

- `fetch_page(token)` must fetch exactly one page and return an object with
  `.data` and `.next_page_token`. Constructing an SDK `ResourceIterator`
  fetches exactly one page, so return it and never iterate it. A paged
  response model such as `SearchUsersResponse` works too.
- The default is one page. `--all` fetches every page, and
  `--max-pages N` stops after N pages.
- In JSON, `nextPageToken` says where to resume.
- Some endpoints return a `nextPageToken` on every page, even when there is
  nothing more yet (audit log files without an end date: clients poll for
  new files), so `--all` would never end. Pass `stop_at_empty_page=True`:
  paging then also stops at the first page without items, and that page's
  `nextPageToken` is returned for picking up new items later
  (`pltr audit list`).
- As a backstop for every command, paging stops with a warning when the API
  returns a page token that was already sent in the same listing (the next
  request would read a page already read); that token is returned.

**Binary output.** For file content, Arrow/Parquet results and images, mark
the command `@pltr_command(..., binary=True)` (the manifest then reports
`outputFormats: ["binary"]`), call `check_binary_output(output)` before the
request and `emit_bytes(chunks, output=output)` after it. `chunks` is `bytes` or an
iterable of `bytes` (an SDK streamed response's `iter_bytes()`, so large
files aren't held in memory). The data goes to `--output FILE` (`-` means
stdout), or to stdout, but never to a terminal (a usage error, exit code 2).
When the output path is an optional argument rather than `--output` (`None`
meaning stdout), pass `output_hint=` (for example `"an OUTPUT_PATH (or - for
stdout)"`) to both, so the message names it.

A file is written through `write_bytes_atomically(path, chunks)`: the data
goes to a temporary file next to it, which replaces the file only once the
stream is complete. A failed download leaves no partial file and keeps an
existing one. The file gets the permissions `open(path, "wb")` would give
it, a symlink's target is replaced, and a path that isn't a regular file
(`/dev/null`, a FIFO) is written directly. Services that download to a path
use the same function.

**Messages.** `success(msg)`, `info(msg)`, `warn(msg)` and
`with spinner(msg): ...` all write to stderr. The first two are suppressed in
JSON mode, `warn` becomes a JSON line, and the spinner only draws on a
terminal. Python `warnings` raised while a command runs (for example the
SDK's `preview` UserWarning) are routed through `warn` automatically.

## Errors and exit codes

The decorator turns any exception into a structured error and an exit code.
Commands contain no `try/except` for reporting.

| Exit | `type` | When |
|---|---|---|
| 0 | | success |
| 1 | `unexpected_error`, `aborted` | a bug or unknown failure (including an unexpected failure inside the SDK); "no" at a confirmation prompt |
| 2 | `usage_error`, `confirmation_required` | bad or missing arguments, invalid JSON input, an invalid RID, a destructive command without `--yes` when stdin is not a terminal |
| 3 | `auth_error` | no usable profile or credentials, an OAuth token request refused (400, 401, 403), HTTP 401 |
| 4 | `permission_denied` | HTTP 403 |
| 5 | `not_found`, `api_not_found` | HTTP 404 (`api_not_found`: 404 with no body, so the endpoint isn't on this stack) |
| 6 | `validation_error` | HTTP 400, 422 |
| 7 | `conflict`, `request_too_large`, `rate_limited`, `server_error`, `api_error`, `invalid_response`, `network_error`, `timeout` | 409, 413, 429, 5xx, other API errors, a response the SDK can't read (`invalid_response`: it doesn't match the SDK's model, or isn't JSON), connection and timeout errors |

JSON mode prints one compact object as the last stderr line, and leaves out
keys that don't apply:

```json
{"type":"not_found","message":"FolderNotFound: The given Folder could not be found. (folderRid=ri.compass.main.folder.x)","exitCode":5,"statusCode":404,"errorCode":"NOT_FOUND","errorName":"FolderNotFound","errorInstanceId":"...","parameters":{"folderRid":"ri.compass.main.folder.x"}}
```

Text mode prints `Error: <message>`, then the details and a hint.

- **Sources.** The layer maps:
  - foundry_sdk exceptions, including typed ones such as `FolderNotFound`.
    Typed errors have an empty `str()` and no `error_code`, so the message is
    built from `errorName`, the description and the parameters, and
    `errorCode` is derived from the HTTP status where that is unambiguous.
  - The SDK's `SDKInternalError`, which is never a usage error: an error
    response whose body isn't a Foundry error is classified by its HTTP
    status, an OAuth token request refused with 400, 401 or 403 is an
    `auth_error` (other statuses, such as 429 and 5xx, are classified by
    status: they aren't about the credentials), a success body that isn't
    JSON is an `invalid_response` (exit 7), and anything else is
    an `unexpected_error` (exit 1, "foundry-platform-sdk failed
    unexpectedly", with a hint to report it).
  - `requests.HTTPError`, including the Foundry error body, for the labeled
    direct-HTTP commands. A success body that isn't JSON
    (`requests.JSONDecodeError` from `response.json()`) is an
    `invalid_response` (exit 7), not invalid user input.
  - pltr `AuthError` and its subclasses.
  - Click usage errors.
  - pydantic validation errors. Where one was raised decides what it means:
    - in the SDK's argument check (`pydantic.validate_call`; the error's
      title is the method, e.g. `FolderClient.get`): a bad RID or value is a
      usage error, a wrong SDK signature is reported as a pltr bug (exit 1);
    - in SDK code after that check, i.e. while decoding the response (the
      title names the model, e.g. `Folder`): an `invalid_response` (exit 7)
      whose message names the model and the mismatched fields and suggests
      upgrading pltr and the SDK (the stack may be newer than the SDK);
    - in pltr's own code (no SDK frames): a usage error. Prefer wrapping
      such validation in `typer.BadParameter`.
  - `json.JSONDecodeError` on its own: a usage error ("Invalid JSON input").
    Parse JSON options with `load_json_input`, which reports the option.
- **Exception chains.** The `__cause__`/`__context__` chain is searched from
  the outside in. The first exception with a known meaning decides the
  classification, and the outer exception's first line is kept as context.
- **Usage errors.** Raise `typer.BadParameter("...", param_hint="'--x'")`. In
  text mode click renders it as usual; in JSON mode it becomes a
  `usage_error`. For JSON inputs (inline, `@file.json` or `@-` for stdin) use
  `load_json_input(value, param_hint="'--where'")`; it reads files and stdin
  as UTF-8 (with or without a byte order mark), UTF-16 or UTF-32.
- **pltr's own failures.** For a failure that isn't an API error, raise
  `PltrError(message, error_type=..., exit_code=..., hint=...)`.
- **Passed through:** `typer.Exit` and `click.Abort`.
- **Debugging:** `PLTR_DEBUG=1` re-raises the exception after rendering it,
  so you see the traceback.
- **Secrets:** bearer tokens and Authorization header values are redacted
  from every rendered message (`redact_secrets`), whatever raised it, for
  example a stored token with a trailing newline that the HTTP library
  rejects as `Illegal header value b'Bearer ...\r'`.
- **Parse-time errors.** Click's own errors (a missing argument, an unknown
  option) are rendered as JSON when the invocation asked for JSON (`--format
  json`/`-f json` among the arguments, or `PLTR_FORMAT=json`). This works
  for every command run through the `pltr` root group. A sub-app invoked
  directly in a test keeps click's text rendering for parse errors.

## Confirmation (destructive commands)

```python
@app.command("delete")
@pltr_command(sdk="filesystem.Space.delete", beta=True, destructive=True)
def delete_space(
    space_rid: SpaceRid,
    yes: YesOption = False,
    confirm: ConfirmAliasOption = False,  # only if --confirm existed before
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Delete an empty space (delete its projects and resources first)."""
    confirm_destructive(f"Delete space {space_rid}?", yes=yes)
    SpaceService(profile=profile).delete_space(space_rid)
    success(f"Deleted space {space_rid}")
    emit(None, format=format)  # JSON: null
```

- **Behaviour of `confirm_destructive`:**
  - `--yes` (or a deprecated alias) returns at once.
  - When stdin is not a terminal it raises `ConfirmationRequired`
    (`confirmation_required`, exit 2, "Re-run with --yes").
  - Otherwise it prompts on stderr; anything but `y`/`yes` raises `Aborted`
    (exit 1).
- **Which commands are destructive:** delete, remove, revoke, reset, cancel,
  abort, replace, clear, undeploy, put-schema and similar. Mark them
  `destructive=True` and give them `YesOption`. The contract test checks
  that every destructive command has `--yes`.
- Never call `typer.confirm`/`typer.prompt` in a converted command.

## Beta endpoints

- In the service, pass a literal `preview=True`, never `preview=preview`.
- Mark the command `beta=True` in `@pltr_command`. The decorator prefixes
  the docstring with `[beta]`, so the help text must come from the
  docstring.
- If the command had a `--preview` flag, keep it as `PreviewNoopOption`.
- The contract test checks that `beta` matches the SDK (some listed method
  has a `preview` parameter) and that the help starts with `[beta]`.

## Command metadata

```python
@pltr_command(
    sdk=("filesystem.Space.get", "filesystem.Space.replace"),  # paths relative to FoundryClient
    http=(),            # labeled direct-HTTP commands only: ("POST /foundry-schema-inference/api/...",)
    beta=True,          # calls a beta endpoint
    destructive=False,  # asks for confirmation, has --yes
    paged=False,        # returns a paged list, has the paging options
    binary=False,       # writes raw bytes (emit_bytes), not table/JSON/CSV
)
```

- **Where it lives:** the metadata is stored on the callback and survives
  Typer's wrapping.
- **Reading it:**
  - `iter_commands(root)` yields
    `CommandEntry(path, command, meta)` for every runnable command,
    including hidden ones and groups with `invoke_without_command`. `root`
    is `pltr.cli.app` or a click group.
  - `get_command_meta(click_command)` reads a single command.
  - `CommandMeta.to_dict()` serializes the metadata for the manifest.
- **What the contract test checks:** every SDK path resolves on a real
  `FoundryClient`, and every converted command has metadata.

## Tests

- **Use `stub_foundry_http`** (`tests/conftest.py`) for service and command
  tests. It provides a real `FoundryClient` with only HTTP faked.
  - `stub.respond(status=200, json=...)` queues one response;
    `stub.respond_always(...)` answers every unqueued request.
  - `stub.requests` holds the recorded `httpx.Request`s. Calls made through
    `requests`, by the direct-HTTP commands, are recorded and answered too,
    and the fake `AuthManager.get_auth_context()` returns the stub host and
    token.
- **Use `tests/foundry_json.py`** for realistic bodies: `folder()`,
  `resource()`, `space()` and `error(name, code, parameters)`. Principal IDs
  must be UUIDs and times ISO-8601, so that the SDK decodes the bodies into
  real models. `sdk_json(body)` gives the JSON pltr prints for a body (times
  re-serialized in UTC). Add builders for your models there.
- **Assert on the outgoing request:** method, `request.url.path`,
  `dict(request.url.params)` and `json.loads(request.content)`. For beta
  calls also assert `request.url.params["preview"] == "true"`.
- **Catch stray `preview=`.** Add
  `pytestmark = pytest.mark.filterwarnings("error::UserWarning")`, so a GA
  call that still passes `preview=` fails.
- **Assert on the right stream:** data is in `result.stdout`, messages and
  errors in `result.stderr` (click 8.2 keeps them separate). In JSON mode,
  parse the last stderr line:
  `json.loads(result.stderr.strip().splitlines()[-1])`.
- **Output formats:**
  - Assert that the JSON equals the SDK serialization, for example
    `json.loads(result.stdout) == fj.sdk_json(body)`.
  - Parse CSV with `csv.DictReader`.
  - For tables, assert the key values appear. The `isolated_home` fixture
    sets `COLUMNS=200` so tables don't wrap, and also keeps
    `~/.cache/pltr` out of your home.
- **Prompts:** monkeypatch `pltr.contract.options.stdin_is_interactive` to
  return `True` and pass `input="y\n"`. Without it, CliRunner's stdin is
  not a terminal, so you get exit code 2.

## The contract test

`tests/test_contract/test_cli_contract.py` walks the whole CLI. For every
command that calls the API, it synthesizes the required arguments and runs
the command with `--format json` (and `--yes` if present) against
`stub_foundry_http`. Every request is answered once with a Foundry 404 body
and once with a 400 body. The test then asserts:

- exit codes 5 and 6;
- empty stdout;
- JSON Lines on stderr, with the structured error (`errorName`,
  `errorInstanceId`, `statusCode`) on the last line;
- for converted commands, a success run from the `SUCCESS` case: exit 0,
  exactly one JSON document on stdout, and no error on stderr.

**Per-module case files.** Cases live in one file per command module, so
parallel conversions don't conflict:
`tests/test_contract/cases/<module>.py`. Each file can define:

- `NOT_CONVERTED`: commands that don't follow the contract yet. They are run
  too, and the test fails once one of them passes, so the set only shrinks.
  **Delete your commands from it.**
- `SUCCESS`: `{path: [respond-kwargs, ...]}`, the responses queued for the
  success run, for example `[{"json": fj.folder()}]` or
  `[{"status_code": 204}]`. Every converted command needs one.
- `ARGS`: `{path: [...]}`, a full argument list that replaces the
  synthesized required arguments. Use it when the generic values don't fit,
  such as JSON input, or a command that needs at least one optional flag.
  RID-like parameters (named `*rid`/`*rids`, or with "RID" in their help)
  get `CONTRACT_RID`; others get `"contract-test"`, `1`, the first choice,
  or a temporary file.
- `LOCAL`: commands that make no API call, each with a
  reason.
- `SUCCESS_EXEMPT`: `{prefix: reason}`, command-path prefixes whose commands
  don't need a `SUCCESS` case. The error checks still run. It's meant for
  the generated `pltr api` tree, whose generator tests the success path.
  Curated commands don't use it.

## Changelog

Add your entries under `## [Unreleased]` in `CHANGELOG.md`, in the Keep a
Changelog sections (`Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`),
and mark changes that break scripts with **Breaking**. Record every removed
command, renamed or removed flag, changed default and changed output shape.
For a converted module that always includes:

- the JSON switch (camelCase SDK fields, no nulls, the paged shape);
- status messages moving to stderr;
- the new exit codes;
- paging defaults, if they changed;
- `[beta]` labels;
- deprecated aliases.

Say in the pull request what you couldn't verify against a live stack, and
update the README and `docs/` examples you changed; `tests/test_docs_examples.py`
fails on examples that name a command or option that doesn't exist.

## Gotchas

- Don't print with `console.print`, `typer.echo` or `print` in a command.
  If it's data, `emit` it; otherwise use `info`/`success`/`warn`. Every
  command prints only through `pltr.contract`.
- `emit` must be called once per command, with the command's `format`.
- Keep `cache_rid(...)` calls for RID completion, after the call succeeds.
- Don't call `iter()` or `list()` on a `ResourceIterator` you want one page
  of: iterating it fetches every page.
- Import foundry-platform-sdk (models, errors) inside the functions that use
  it, not at module level: `pltr --help` and every shell completion import
  every command module, and the SDK's model packages take about half a
  second to import. `tests/test_startup.py` fails if startup imports
  `foundry_sdk`. Under `if TYPE_CHECKING:` is fine.
- Every command is converted, so the legacy helpers are gone:
  `pltr.utils.formatting.OutputFormatter`, `pltr.utils.progress`
  (`SpinnerProgressTracker`, ...), `pltr.utils.pagination` and
  `BaseService._serialize_response`/`_paginate_*`. The "Before" example above
  shows how they were used; use `emit`, `spinner` and `collect_pages`.
