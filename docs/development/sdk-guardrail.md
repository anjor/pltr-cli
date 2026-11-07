# SDK call guardrail

pltr is a thin layer over [`foundry-platform-sdk`](https://github.com/palantir/foundry-platform-python).
Every command should end in an SDK call that exists, with arguments the SDK accepts. Service
tests used to mock the SDK with bare `Mock()` objects, which accept any attribute and any
argument, so about 40 commands shipped that could never succeed (#182, #184). The guardrail
(#185) has two parts:

1. **A static check** of every SDK call in pltr against the real SDK, run in CI by
   `tests/test_sdk_call_guardrail.py` with a ratchet allowlist.
2. **Real-SDK service tests**: new and changed service tests use the `stub_foundry_http` fixture.

## What the check does

`scripts/sdk_calls.py` parses `src/pltr/services/*.py` and `src/pltr/commands/*.py`. For each
SDK call it:

- resolves the call target: `self.service...` (through the class's `_get_service()`),
  `self.client...`, service properties and accessor methods that return an SDK object,
  composed services (`self.dataset_service.service...`), simple local aliases
  (`svc = self.service`, `create = self.service.Project.create`) and `getattr(obj, "name")`
  with a literal name;
- looks the target up on a real `FoundryClient` built with a dummy token and hostname
  (no network);
- binds the call's arguments to the real signature with `inspect.Signature.bind`, using
  placeholder values.

It runs in about two seconds, most of it importing the SDK modules pltr uses.

### Rules

| Rule | Fails when |
|---|---|
| `missing-method` | The namespace, resource or method doesn't exist in the installed SDK. |
| `unknown-keyword(<name>)` | A keyword argument the method doesn't accept. |
| `too-many-positional` | More positional arguments than the method takes (usually a keyword-only argument passed positionally). |
| `missing-required(<name>)` | A required argument isn't passed. |
| `duplicate-argument(<name>)` | An argument is passed both positionally and by keyword. |
| `bad-arguments` | `inspect.Signature.bind` rejects the arguments for a reason the rules above don't name (a fallback, so the check never disagrees with `bind`). |
| `preview-on-ga` | `preview` is passed to a GA method (one without a `preview` parameter). The SDK drops it and prints a warning on every call. |
| `beta-without-preview` | A beta method (one with a `preview` parameter) is called without `preview`. The server rejects it with `ApiFeaturePreviewUsageOnly`. |
| `beta-preview-not-literal` | A beta method gets `preview=` something other than the literal `True`, e.g. `preview=preview`. That's how the "beta command only works with `--preview`" bug happens. |
| `unchecked-kwargs` | Arguments go through `**kwargs` (usually a dict built up with `params["x"] = ...`) or `*args`, so the call can't be checked. Explicit arguments next to the `**` are still checked. |
| `uncheckable` | The target can't be pinned down statically: an attribute name computed at runtime, a `_get_service()` the checker can't resolve, an SDK object passed to other code (for example an SDK method handed to a helper as a callback), where the call that uses it can't be seen, or an SDK client built with `get_client(...)` anywhere but `src/pltr/services/base.py` (the calls made with it can't be followed; go through a service's `self.client`/`self.service`). |
| `direct-http` | A direct HTTP call (`requests.*`, `httpx.*`, `urllib.request.urlopen`, `BaseService._make_request`, ...) outside the labeled exceptions. |

Beta means the SDK method has a `preview` parameter. The rule follows the roadmap's decision:
GA endpoints never get `preview`; beta endpoints always get `preview=True`.

### Labeled direct-HTTP exceptions

New work goes through the SDK. These existing functions are the only ones allowed to call
Foundry endpoints directly (`LABELED_HTTP_EXCEPTIONS` in `scripts/sdk_calls.py`). The list
doesn't grow:

| Function | Command |
|---|---|
| `services/dataset.py::DatasetService.apply_schema` | `dataset schema apply` |
| `services/ontology.py::ObjectTypeService._create_schema_entity` | `ontology object-type-create` / `link-type-create` fallback |
| `services/language_models.py::LanguageModelsService.enroll_model` | `language-models enroll` |
| `services/base.py::BaseService._make_request` | the shared helper they use |

`pltr verify` calls `admin.User.get_current()` through the SDK (#190).

### What it can't see

The check follows names, not data. It can't follow SDK objects through function parameters
or containers (it reports SDK objects handed over that way as `uncheckable`), can't see
inside a `**kwargs` dict (hence `unchecked-kwargs`), and can't check argument *values*
(passing `None` for a required list) or how responses are used (a formatter reading a field
the model doesn't have, #183). The `stub_foundry_http` tests below cover those.

## Running it

```bash
uv run pytest tests/test_sdk_call_guardrail.py          # what CI runs (also part of `pytest tests/`)
uv run python scripts/check_sdk_calls.py                # new/stale violations; exit 1 if any
uv run python scripts/check_sdk_calls.py --all          # every violation, allowlisted ones too
uv run python scripts/check_sdk_calls.py --json         # one record per SDK/HTTP call
uv run python scripts/check_sdk_calls.py --write-allowlist
```

## Reading a failure

```text
1 new SDK call violation(s):

  src/pltr/services/folder.py:57  FolderService.rename_folder
    filesystem.Folder.get: unknown-keyword(display_name)
    filesystem.Folder.get(folder_rid) has no parameter 'display_name'
    key: services/folder.py::FolderService.rename_folder::filesystem.Folder.get::unknown-keyword(display_name)
```

- The first line is where the call is and which service method it's in.
- `filesystem.Folder.get` is the SDK method, as a path from `FoundryClient`
  (`client.filesystem.Folder.get`). For `missing-method` it's the path pltr tried; the message
  names the closest existing attributes.
- The message shows the real signature (without `request_timeout` and `_sdk_internal`).
- The key identifies the violation in the allowlist:
  `<file under src/pltr>::<Class.method>::<SDK path or HTTP call>::<rule>`, plus `[2]`, `[3]`,
  ... when the same call breaks the same rule more than once in one method. Keys contain no
  line numbers, so unrelated edits don't change them.

To see the real signature yourself:

```bash
uv run python -c "import inspect; from foundry_sdk.v2.filesystem.folder import FolderClient; print(inspect.signature(FolderClient.get))"
```

## Fix, don't allowlist

`tests/sdk_call_allowlist.txt` listed the violations that existed when the check landed, each
with a reason; they have all been fixed, so it holds no entries. The test fails on any
violation that isn't listed **and** on any listed entry that no longer occurs, so the list can
only shrink:

- **When you fix a call, delete its line(s).** The stale-entry test tells you which.
- **When you rename or move a method that still has listed violations**, the keys change. Run
  `uv run python scripts/check_sdk_calls.py --write-allowlist` (it keeps existing reasons)
  and check the diff only renames entries.
- **Don't add entries for new code.** Fix the call instead:
  - `missing-method`: find the real method (the message lists the closest ones; the SDK is
    the source of truth, see `.venv/lib/python3.*/site-packages/foundry_sdk/v2/`). If the SDK
    has no equivalent, remove the command (CLAUDE.md: remove non-working commands rather than
    showing confusing errors).
  - `unknown-keyword`, `too-many-positional`, `missing-required`: match the signature in the
    message. Most SDK arguments after the path parameters are keyword-only.
  - `preview-on-ga`: drop `preview`. `beta-*`: pass the literal `preview=True` and label the
    command `[beta]` in its help.
  - `unchecked-kwargs`: pass explicit keywords. For an optional argument the user didn't
    give, pass `None`: the SDK leaves `None` query parameters and body fields out of the
    request, so there's no need to build a dict.
  - `uncheckable`: call the SDK method directly where the arguments are known.
  - `direct-http`: use the SDK. The labeled exceptions above are the only exceptions.
- An allowlist entry for new code needs a reason a reviewer will accept, such as a known SDK
  bug with a link. `--write-allowlist` writes the violation message as the reason for new
  entries; replace it with the real reason.

## Service tests use the real SDK client

New and changed service tests use the `stub_foundry_http` fixture from `tests/conftest.py`.
It gives the service a real `FoundryClient` and fakes only `httpx.Client.send`, so SDK
argument validation runs, a missing method or a wrong keyword fails the test, and responses
decode into real SDK models.

- Assert on the outgoing request: method, path, query and body.
- Mark tests with `@pytest.mark.filterwarnings("error::UserWarning")` so a GA call that still
  passes `preview=` fails.
- For beta calls, assert `preview=true` in the query.
- Feed realistic responses in the Foundry API's JSON shape (camelCase field names, as in the
  SDK models' aliases), so they decode into real models and formatters read real fields.
- Don't migrate test files just for the sake of it. When you touch a `Mock()`-based service
  test file, migrate it.

```python
import pytest

from pltr.services.space import SpaceService

SPACE_RID = "ri.compass.main.folder.3b7c2bb4-37a6-4ad9-9b6c-3a0a3c3f3a1e"
ORG_RID = "ri.multipass..organization.6c2f8d0a-6a1b-4f0e-8b7e-2f1d5c9a0b3d"


@pytest.mark.filterwarnings("error::UserWarning")
def test_get_space_calls_the_beta_endpoint_with_preview(stub_foundry_http):
    stub_foundry_http.respond(
        json={
            "rid": SPACE_RID,
            "displayName": "Analytics",
            "path": "/Analytics",
            "fileSystemId": "default",
            "usageAccountRid": "ri.resource-policy-manager.global.usage-account.1a2b3c",
            "organizations": [ORG_RID],
            "deletionPolicyOrganizations": [ORG_RID],
            "defaultRoleSetId": "default-role-set",
        }
    )

    # The response decodes into the SDK's real Space model; a missing required
    # field or a renamed method would fail here.
    SpaceService().get_space(SPACE_RID)

    [request] = stub_foundry_http.requests
    assert request.method == "GET"
    assert request.url.path == f"/api/v2/filesystem/spaces/{SPACE_RID}"
    assert request.url.params["preview"] == "true"  # Space.get is beta
```

Then assert on the decoded output the command prints, using fields that exist on the model.

## Reusing the resolver

Other tooling (for example cross-checking which SDK methods curated commands call, or the
coverage report) can use the same resolver. It needs no network:

```python
from scripts.sdk_calls import collect_sdk_calls

for call in collect_sdk_calls():
    # call.file ("services/folder.py"), call.class_name, call.method, call.line,
    # call.kind ("sdk" or "http"), call.sdk_path ("filesystem.Folder.get"),
    # call.resolved, call.beta, call.signature, call.http_label, call.violations
    ...
```

`scripts/` is importable from the repository root (tests run from there); scripts run as
files can add the root to `sys.path`, as `scripts/check_sdk_calls.py` does.
`uv run python scripts/check_sdk_calls.py --json` prints the same records as JSON.

## Bumping the SDK

See the checklist in [RELEASE.md](../../RELEASE.md#checklist-bumping-foundry-platform-sdk).
Upstream release notes mostly say "No documented user-facing changes", so this check is the
real changelog for the calls pltr makes.
