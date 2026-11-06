### Breaking

- **`PLTR_PROFILE` naming a profile that doesn't exist is now an error** ("Profile 'x' not found (selected by PLTR_PROFILE)"). It used to fall back silently to the default profile.
- **`pltr verify` output and exit codes changed.** It now calls `admin.User.get_current()` through the SDK (not `/multipass/api/me`):
  - table output shows the auth source, auth type, host and the `admin.User` fields (username, name, email, user ID, organization, realm, status); the groups row is gone;
  - status lines ("Verifying ...", "✓ Authentication successful") and errors go to stderr; stdout carries only the result;
  - failures exit with 3 (no usable credentials, rejected token or OAuth client credentials, unusable keyring), 4 (permission denied), 5 (endpoint not found) or 7 (network or other API error) instead of 1.
- **OAuth clients need the `api:admin-read` scope for `pltr verify`** (the scope `User.get_current` requires). Without it verify reports "Permission denied (HTTP 403)" and exits 4.
- **`pltr configure` exits with code 3** and a message pointing to environment-variable auth when the system keyring can't be used (it used to crash with a traceback).
- **Direct-HTTP commands always use `https://`** with the profile's or environment's host, like the SDK client (the scheme in a stored host used to be used as typed, and a host without a scheme failed).
- `TokenAuthProvider` and `OAuthClientProvider` no longer read `FOUNDRY_*` environment variables; only `AuthManager` does (internal API).

### Added

- **Environment-variable auth without a stored profile.** When no profile is selected, pltr uses `FOUNDRY_HOST` with `FOUNDRY_TOKEN`, or `FOUNDRY_HOST` with `FOUNDRY_CLIENT_ID` and `FOUNDRY_CLIENT_SECRET` (the token wins if both are set). `FOUNDRY_HOSTNAME`, the Foundry SDK's name, is accepted when `FOUNDRY_HOST` isn't set. Hosts work with or without `https://`. This path needs no configuration directory and never touches the system keyring (#190, #144).
- Documented precedence: `--profile`, then `PLTR_PROFILE`, then the default profile, then the environment variables. An environment variable never overrides, or fills gaps in, a stored profile.
- `pltr verify --format table|json|csv` (`-f`; default from `PLTR_FORMAT`). JSON output is `{"authSource": {...}, "user": {...}}`: `authSource` has `kind` (`profile` or `environment`), `profile` and `selectedBy` (`--profile`, `PLTR_PROFILE` or `default`) for profiles, `authType` (`token` or `oauth`), `host`, and `variables` for environment auth; `user` is the SDK `User` model in API field names. In JSON mode a failure writes one JSON error object to stderr.
- `PLTR_KEYRING_TIMEOUT`: seconds to wait for the system keyring (default 30; `0` waits indefinitely).
- `AuthManager.resolve_auth_source(profile)` (which credentials a command would use, without reading secrets) and `AuthManager.get_auth_context(profile)` (`AuthContext`: source, SDK client, SDK auth object, `base_url`, `get_token()`).

### Changed

- Reading settings or profiles no longer creates `~/.config/pltr` (or `$XDG_CONFIG_HOME/pltr`); it is created when something is saved.
- Keyring calls run with a time limit, and any keyring failure (missing backend, backend error, timeout) raises `KeyringUnavailableError` (a `MissingCredentialsError`), whose message points to the environment variables and, for the default profile, names the file that sets it.

### Removed

- The client-level `FoundryClient(..., preview=True)` attempt and its fallback in `auth/token.py` and `auth/oauth.py`; the V2 client has never accepted `preview` (#184).
- `pltr verify` no longer calls the internal `/multipass/api/me` endpoint or requests OAuth tokens itself; one fewer direct-HTTP exception.

### Fixed

- `FOUNDRY_HOST` plus `FOUNDRY_TOKEN` (or OAuth client credentials), as documented in the README, failed with "No profile specified and no default profile configured" unless a stored profile existed.
- Direct-HTTP commands (`dataset schema apply`, the `ontology object-type-create` / `link-type-create` fallback, `language-models list/status/enroll`) sent `Authorization: Bearer None` for OAuth profiles and ignored environment-variable auth. They now take the host and token from the same SDK auth object as the command's SDK client, so token, OAuth and environment auth all work, and one OAuth token is shared by SDK and direct calls.
- A system keyring that blocks (for example the macOS Keychain over SSH or in an agent sandbox) no longer hangs pltr indefinitely; a missing keyring backend gives a clear error instead of a traceback (#144).
- Corrupted stored credentials give a clear "unreadable, run `pltr configure configure --profile NAME`" error instead of a JSON decoding traceback.

### Docs to update

- `docs/user-guide/commands.md` (`pltr verify`): add `--format/-f` (table, json, csv; `PLTR_FORMAT`), the JSON shape above, the auth-source report and exit codes 0/3/4/5/7.
- `claude_skill/SKILL.md` and `claude_skill/reference/quick-start.md`: document the precedence (`FOUNDRY_*` variables are used only when no profile is selected, so a default profile wins), that environment-variable auth needs no keyring or configure step, and `pltr verify --format json` as the agent's first check (#190 asks for the precedence in the agent skill).
- `docs/user-guide/troubleshooting.md` ("Environment Variable Debugging", "Check Configuration Files"): environment variables are ignored when a profile is selected; keyring errors and `PLTR_KEYRING_TIMEOUT`; `pltr verify --format json` shows the auth source.
- `docs/user-guide/quick-start.md` and `docs/user-guide/workflows.md` (environment-variable examples): they now work as written, but add that a default profile on the same machine takes precedence.
- `tests/integration/test_auth_flow.py` and `tests/integration/test_cli_integration.py`: skipped tests still patch `pltr.commands.verify.requests.get`, which no longer exists; rewrite them against a faked HTTP layer if they are ever unskipped.

### Not verified live

- `admin.User.get_current()` succeeds for user tokens and for OAuth service users that have the `api:admin-read` scope, and returns 403 `GetCurrentUserPermissionDenied` without it (from the SDK docstring; not checked against a stack).
- The OAuth client-credentials token request for direct-HTTP calls goes through the SDK's `ConfidentialClientAuth`, which learns its host from the SDK client; tested with a faked network only.
- A client-credentials token request without scopes returns a token with all scopes granted to the client (per the SDK docstring).
- The keyring time limit was tested with a fake backend that blocks; not with a real macOS Keychain or Secret Service prompt.
