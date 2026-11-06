### Added

- CI guardrail for SDK calls (#185). `tests/test_sdk_call_guardrail.py` resolves every
  `foundry-platform-sdk` call in `src/pltr/services` and `src/pltr/commands` against a real
  `FoundryClient` (dummy credentials, no network), binds the arguments to the real signatures,
  and enforces the preview rules (GA methods never get `preview`; beta methods always get the
  literal `preview=True`). It also flags calls whose arguments go through `**kwargs`, calls it
  can't resolve, and direct HTTP outside the labeled exceptions (`dataset schema apply`, the
  `ontology object-type-create` / `link-type-create` fallback, `language-models list/status/enroll`).
- Ratchet allowlist `tests/sdk_call_allowlist.txt` with the 170 violations found on SDK 1.111.0,
  each with a reason. The test fails on any new violation and on any entry that no longer
  occurs, so each fix deletes its entries.
- `scripts/check_sdk_calls.py`: prints violations grouped by file and rule (`--all`), dumps every
  SDK/HTTP call as JSON (`--json`), and rewrites the allowlist keeping existing reasons
  (`--write-allowlist`). The resolver behind it, `scripts/sdk_calls.py` (`collect_sdk_calls()`),
  returns one structured record per call for other tooling.
- Developer docs: `docs/development/sdk-guardrail.md` (rules, reading a failure, fix vs.
  allowlist, `stub_foundry_http` for service tests) and an SDK-bump checklist in `RELEASE.md`.

### Changed

- `docs/api/wrapper.md` now shows service tests written with the `stub_foundry_http` fixture
  instead of `Mock()` clients.

### Docs to update

- `README.md` "Development" / "Contributing": link `docs/development/sdk-guardrail.md`, and say
  that service tests use `stub_foundry_http` and that `uv run pytest` includes the SDK call check.
- `README.md` lists commands the check shows can never succeed today (fixes are owned by other
  agents; update the examples when they land): `pltr orchestration builds search` (lines 86, 166,
  202: `Build.search` requires `where`), `pltr connectivity import file` / `import table`
  (lines 178-179: `client.file_imports` / `client.table_imports` don't exist).

### Not verified live

- Nothing here talks to Foundry. The violations come from SDK 1.111.0 signatures, not a live
  stack. The broken commands found beyond #182 (`connectivity import file`, `table`,
  `list-file`, `list-table`, `get-file`, `get-table`, `admin group create`, `admin marking create`,
  `admin org create`, `orchestration builds search`, `space list --organization-rid`) were
  confirmed by calling the real SDK client with HTTP blocked: the SDK has no such attribute or
  rejects the arguments before sending a request. `connectivity connection list` doesn't fail
  but always takes its filesystem-scan fallback, because the SDK has no `Connection.list`.
