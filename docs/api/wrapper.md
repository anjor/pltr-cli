# The Service Layer and pltr's Architecture

A guide for developers: how pltr is put together, how to write a service
method, and where to look when you add a command. The rules every command
follows (output, errors, exit codes, confirmation, beta endpoints) are in
[the command contract](../development/command-contract.md); this page doesn't
repeat them.

## Architecture

```
pltr (src/pltr/cli.py: the Typer app; main() resolves aliases, then runs it)
  ├── curated commands   src/pltr/commands/<group>.py    on pltr.contract
  │     └── services     src/pltr/services/<area>.py      thin SDK wrappers
  ├── pltr api           src/pltr/commands/api/           generated from the SDK
  └── pltr commands      src/pltr/commands/manifest.py    the command manifest
                              ↓
        foundry-platform-sdk FoundryClient (from pltr.auth.AuthManager)
                              ↓
                      Foundry Platform API
```

- **Commands** declare their arguments and options with Typer, record their
  metadata with `@pltr_command` (SDK methods, beta, destructive, paged), and
  print through `pltr.contract` (`emit`, `success`, `warn`, ...). They don't
  catch exceptions: the contract turns them into structured errors and exit
  codes.
- **Services** call the SDK and return what it returns: models, iterators or
  responses. They hold no formatting logic.
- **`pltr.contract`** (`src/pltr/contract/`) is the shared layer: output
  formats, error classification and exit codes, confirmation, paging,
  options and command metadata.
- **Generated commands** (`pltr api`) are built from specs that
  `scripts/generate_api_commands.py` writes from the installed SDK; see
  [`pltr api`](../api-commands.md#for-maintainers).
- **Auth and config** (`src/pltr/auth/`, `src/pltr/config/`) resolve the
  credentials (profile or environment variables) and build the SDK client.

## Project Structure

```
src/pltr/
├── cli.py              # the root Typer app and the console-script entry point
├── __main__.py         # python -m pltr
├── manifest.py         # builds the command manifest (pltr commands)
├── auth/               # AuthManager, token and OAuth providers, keyring storage, env-var auth
├── config/             # profiles, settings, aliases
├── contract/           # output, errors, exit codes, confirmation, options, metadata
├── commands/           # one module per command group (dataset.py, ontology.py, ...)
│   └── api/            # the generated `pltr api` tree (_runtime.py and _specs/)
├── services/           # one service per area (dataset.py, ontology.py, ...)
└── utils/              # helpers for completion and alias resolution
scripts/
├── generate_api_commands.py     # regenerate `pltr api` from the SDK
├── generate_skill_reference.py  # regenerate claude_skill/reference from the manifest
├── check_sdk_calls.py           # the SDK call check (docs/development/sdk-guardrail.md)
├── check_command_metadata.py    # curated commands' sdk= metadata vs. their service calls
├── coverage.py                  # which commands reach each SDK method
└── release.py                   # see RELEASE.md
```

## Services

Every service extends `BaseService` (`src/pltr/services/base.py`):

```python
from typing import Any

from pltr.services.base import BaseService


class FolderService(BaseService):
    """Folder operations (client.filesystem)."""

    def _get_service(self) -> Any:
        return self.client.filesystem   # the SDK namespace this service uses

    def get_folder(self, folder_rid: str) -> Any:
        """Get a folder (Folder.get, GA); returns a Folder model."""
        return self.service.Folder.get(folder_rid)
```

- `BaseService(profile=None)` resolves credentials lazily: `self.client` is
  the SDK's `FoundryClient`, built by `AuthManager.get_client(profile)` the
  first time it is used. `self.service` is what `_get_service()` returns.
- **Return SDK objects unchanged**: a model, the SDK's `ResourceIterator`
  (don't iterate it: constructing one fetches exactly one page), or a
  response. The command decides how to print them.
- **Don't catch SDK exceptions.** If you must add context, raise your own
  exception `from e`, so the error layer still finds the SDK exception.
- **GA methods get no `preview`; beta methods get a literal `preview=True`.**
  A method is beta if its signature has a `preview` parameter. Check with
  `inspect.signature` against the installed SDK.
- **Pass arguments by keyword, explicitly**, never through `**kwargs` or a
  dict, so the SDK call check can bind them to the real signature.
- **Import SDK models inside the methods that use them**, not at module
  level: `pltr --help` and shell completion import every command module, and
  the SDK's model packages are slow to import. `tests/test_startup.py` fails
  if startup imports `foundry_sdk`.
- `self._make_request(method, endpoint, ...)` calls a Foundry endpoint
  directly with the client's host and token. It is only for the labeled
  direct-HTTP exceptions (`dataset schema apply`, the
  `ontology object-type-create`/`link-type-create` fallback and
  `language-models enroll`); new code goes through the SDK.

### Using services from Python

Services can be used as a library. They return SDK models and raise SDK
exceptions:

```python
from pltr.services.dataset import DatasetService
from pltr.services.folder import FolderService

dataset = DatasetService(profile="production").get_dataset(
    "ri.foundry.main.dataset.c26f11c8-cdb3-4f44-9f5d-9816ea1c82da"
)
print(dataset.name, dataset.parent_folder_rid)

children = FolderService().list_children("ri.compass.main.folder.<id>")
for resource in children.data:      # one page; children.next_page_token resumes
    print(resource.display_name, resource.type)
```

`profile=None` uses the same precedence as the CLI: `PLTR_PROFILE`, the
default profile, then the `FOUNDRY_*` environment variables.

## Authentication

`AuthManager` (`src/pltr/auth/manager.py`) picks the credentials:

```python
from pltr.auth.manager import AuthManager

manager = AuthManager()
source = manager.resolve_auth_source("production")   # which credentials, without reading secrets
context = manager.get_auth_context("production")     # source, SDK client, base_url, get_token()
client = manager.get_client("production")            # a FoundryClient
```

The precedence is `--profile`, `PLTR_PROFILE`, the default profile, then the
environment variables; see [Authentication](../user-guide/authentication.md).

## Adding a Command

1. Add the service method, following the rules above.
2. Add the command to `src/pltr/commands/<group>.py` with
   `@pltr_command(...)`, the shared options and `emit(...)`. The
   [command contract](../development/command-contract.md) has the checklist
   and a before/after example.
3. Add tests (below), and a contract-test case in
   `tests/test_contract/cases/<group>.py`.
4. Regenerate the agent skill's reference:
   `uv run python scripts/generate_skill_reference.py`.
5. Record the change under `## [Unreleased]` in `CHANGELOG.md`, and update
   the docs (`tests/test_docs_examples.py` checks their examples).

A new top-level group is registered in `src/pltr/cli.py` with
`app.add_typer(...)`.

## Testing

Service and command tests run against a real `FoundryClient` with only HTTP
faked, through the `stub_foundry_http` fixture (`tests/conftest.py`). Assert
on the outgoing request and on real decoded models:

```python
import json

import pytest

from pltr.services.folder import FolderService
from tests.foundry_json import FOLDER_RID, PARENT_RID
from tests.foundry_json import folder as folder_json

# A GA call that still passes preview= makes the SDK warn: fail on it.
pytestmark = pytest.mark.filterwarnings("error::UserWarning")


def test_create_folder(stub_foundry_http):
    stub_foundry_http.respond(json=folder_json())

    folder = FolderService().create_folder(
        display_name="Test Folder", parent_folder_rid=PARENT_RID
    )

    assert folder.rid == FOLDER_RID
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", "/api/v2/filesystem/folders")
    assert json.loads(request.content) == {
        "displayName": "Test Folder",
        "parentFolderRid": PARENT_RID,
    }
```

Build realistic response bodies with the helpers in `tests/foundry_json*.py`.
For beta endpoints, assert `request.url.params["preview"] == "true"`.
Command tests run the CLI with `typer.testing.CliRunner` and check stdout
(data), stderr (messages and errors) and the exit code.

Run the checks CI runs:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src/pltr
```

`uv run pytest` includes the SDK call check
([sdk-guardrail.md](../development/sdk-guardrail.md)), the CLI-wide contract
test, the freshness of the generated `pltr api` specs and skill reference,
and the docs example check.
