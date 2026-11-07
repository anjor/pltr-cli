### Breaking

- **`admin`: `--format json` prints the SDK's own serialization.** Field names are the Foundry
  API's (camelCase, for example `givenName`, `familyName`, `categoryId`, `markingId`,
  `createdTime`), null fields are left out, and the snake_case keys and `null` values of the old
  `.dict()` output are gone. Lists print `{"data": [...], "nextPageToken": "..."}`
  (`nextPageToken` only when more pages exist): `user list`, `user search`, `group list`,
  `group search`, `marking list`. Other shapes are the API response itself:
  - `user batch-get`, `group batch-get`, `role batch-get`, `marking batch-get`:
    `{"data": {"<ID>": {...}}}`;
  - `user markings`: `{"view": ["<marking ID>", ...]}`;
  - `org available-roles`: `{"data": [...]}`;
  - `user delete`, `user revoke-tokens`, `group delete`: `null`.
- **`admin` status output moved to stderr.** "Results saved to ...", "... created
  successfully", "... deleted successfully" and similar messages, and errors, used to be printed
  on stdout. stdout now carries only data. With `--format json`, informational messages are
  suppressed and errors are one JSON object on the last stderr line.
- **`admin` exit codes:** 2 usage error, 3 authentication, 4 permission denied, 5 not found,
  6 validation, 7 other API or network error (see the README section "Output, errors and exit
  codes"). Every error used to exit with 1.
- **Destructive `admin` commands no longer prompt when stdin is not a terminal**: `user delete`,
  `user revoke-tokens`, `group delete`, `org replace` and `marking replace` fail with exit code 2
  unless you pass `--yes`/`-y`. Answering "no" at the prompt now exits with 1 ("Aborted"); it
  used to print "Operation cancelled." and exit with 0. Prompts are written to stderr.
- **User and group IDs must be UUIDs.** `user get`, `user markings`, `user revoke-tokens`,
  `user delete`, `user batch-get`, `group get`, `group delete` and `group batch-get` reject
  anything else (exit code 2) with a hint to find the ID with `pltr admin user search` or
  `pltr admin group search`. The help used to say "User ID or RID"; usernames, emails, group
  names and RIDs never worked (the SDK rejects them before sending the request).
- **Table and CSV columns of `admin` commands changed.** They are curated and read real SDK
  model fields: users (ID, username, given and family name, email, status; one user also shows
  organization, realm and attributes), groups (ID, name, description, organizations; one group
  also shows realm and attributes), markings (ID, name, category ID, deleted, created; one marking
  also shows description, organization, priority, prominence and created by), organizations (RID,
  name, description, host, marking ID), roles (ID, display name, description, operations,
  inherited roles), available roles (ID, name, role set, default, description). `user markings`
  prints one row per marking ID.
- **`admin` commands validate `--format`/`-f`**: only table, json and csv are accepted
  (case-insensitive).

### Added

- `--yes`/`-y` on `admin user delete`, `user revoke-tokens`, `group delete`, `org replace` and
  `marking replace`.
- `-p` (`--profile`), `-f` (`--format`) and `-o` (`--output`) short flags on every `admin`
  command that has the long option; `PLTR_FORMAT` sets the default format.
- `--max-pages` and `--all` on `admin group list`, `user search`, `group search` and
  `marking list` (`user list` already had them). `user search` and `group search` now page:
  `--page-token` resumes from the `nextPageToken` of an earlier response.
- `admin marking list --include-deleted/--exclude-deleted` (the API includes deleted markings
  when neither is passed) and `--marking-type MANDATORY|CBAC` (#189).
- `admin group create --organization ORGANIZATION_RID` (repeatable, at least one required) and
  `--attribute NAME=VALUE` (repeatable; repeat a name for several values).
- `admin marking create --role ROLE:PRINCIPAL_ID` (repeatable; ROLE is ADMINISTER, DECLASSIFY
  or USE; at least one ADMINISTER is required) and `--member PRINCIPAL_ID` (repeatable).
- `admin org create --description` and `--host`; `admin org replace --host`.
- `[beta]` label in the help of `admin role get`, `role batch-get` and `org create`: they call
  beta Foundry endpoints, always with `preview=true`.
- The help of `admin user`, `group`, `org`, `marking` and `role` explains how each is identified
  (user and group IDs are UUIDs, organizations are RIDs) and where to find the IDs.

### Changed

- `admin org replace` and `admin marking replace` keep the current description (and, for
  organizations, host) unless you pass `--description`/`--host`: they read the organization or
  marking first and send the current values back. `Organization.replace` and `Marking.replace`
  replace the whole object, so the description and host used to be cleared (the host could not
  even be set from pltr). Reading needs view permission on the organization or marking.
- `admin marking create --category-id` is now required (`Marking.create` requires it).
- `admin org create --admin-id` is now required (at least one; `Organization.create` requires
  administrators). It takes user or group IDs (UUIDs).
- `admin user list` without `--page-size` uses the API's default page size; it used to send the
  `page_size` setting (20 by default). This matches the other converted list commands.

### Deprecated

- `--confirm` on `admin user delete`, `user revoke-tokens`, `group delete`, `org replace` and
  `marking replace`: a hidden alias of `--yes` that prints a deprecation warning. It will be
  removed in the next release.
- `admin group create --org-rid`: a hidden alias of `--organization` that prints a deprecation
  warning. It will be removed in the next release.
- `admin org available-roles --page-size` and `--page-token`: hidden, have no effect and print a
  deprecation warning. `Organization.list_available_roles` isn't paged; it returns every role in
  one response. They will be removed in the next release.

### Removed

- For developers: `AdminService.list_users_paginated()` and `AdminService._serialize_response()`.
  `AdminService` methods return SDK models and responses; `AdminService.list_users()`,
  `list_groups()`, `list_markings()`, `search_users()` and `search_groups()` fetch one page.
  `AdminService.get_current_user()` still returns a dict, now the SDK's `User.to_dict()` (API
  field names), for `ProjectService`; `AdminService.current_user()` returns the `User` model.

### Fixed

- `admin user search` and `admin group search` always failed: they passed `query=`, but
  `User.search`/`Group.search` take a `where` filter (#182). They now send
  `{"type": "queryString", "value": QUERY}`: a case-insensitive prefix search over usernames,
  given and family names (users; deleted users aren't included) or group names (groups).
- `admin org available-roles` always failed: it passed `page_size`, `page_token` and `preview`,
  but `Organization.list_available_roles` takes only the organization RID (#182, #184).
- `admin role get` always failed: `Role.get` is beta and was called without `preview` (#182).
- `admin user batch-get`, `group batch-get`, `marking batch-get` and `role batch-get` always
  failed: they sent bare ID strings, which the SDK rejects; the API takes
  `[{"userId": "..."}]`-style elements. `marking batch-get` also passed `preview=` to a GA
  endpoint.
- `admin group create` always failed: `Group.create` requires `organizations` and `attributes`,
  and `organization_rid` isn't a parameter.
- `admin marking create` always failed: `Marking.create` requires `category_id`,
  `initial_members` and `initial_role_assignments`, and the call passed `preview=` to a GA
  endpoint.
- `admin org create` always failed: `Organization.create` requires `administrators`, and
  `admin_ids` isn't a parameter.
- `admin marking list`, `marking get`, `marking replace` and `org replace` no longer pass
  `preview=` to GA endpoints, so the SDK warning is gone (#184).

### Docs to update

- `docs/user-guide/commands.md` (admin section, about lines 1320-1445):
  - user and group examples pass emails or names as IDs (`john.doe@company.com`,
    `engineering-team`, `old-team`); they must be UUIDs, e.g. from `pltr admin user search`;
  - `pltr admin org get my-organization` must take an organization RID
    (`ri.multipass..organization.<id>`); `pltr admin role get admin-role` needs a real role ID
    (from `pltr admin org available-roles`);
  - `--confirm` → `--yes`;
  - `group create` needs `--organization` (and can take `--attribute`);
  - document `org create` (`--admin-id` required, `--description`, `--host`), `org replace`
    (keeps the description and host unless given), `org available-roles` (not paged),
    `role batch-get`, the `marking` commands (`marking create --category-id --role`,
    `marking list --include-deleted/--exclude-deleted --marking-type`), `user batch-get`,
    `group batch-get`, the JSON shapes above, and the `[beta]` commands.
- `claude_skill/reference/admin-commands.md`: the same ID fixes; `group create --org-rid` →
  `--organization`; the `org create` example (`ri.enrollment.main.123`, no `--admin-id`) and
  the `org replace`/`org available-roles` examples (`ri.compass.main.org.123`) need
  `ri.multipass..organization.<id>` RIDs and `--admin-id`; drop `org available-roles --page-size`;
  `marking create` needs `--category-id` and `--role ADMINISTER:<user ID>`; `--confirm` →
  `--yes`; `user list` now documents `--max-pages`/`--all`.
- `claude_skill/workflows/permission-management.md` (lines 11, 138, 141, 154, 157, 163) and
  `docs/user-guide/workflows.md` (lines 272, 433, 437, 440): the same ID, `--organization` and
  `--confirm` fixes.
- `docs/pagination.md` and `docs/migration/v2-pagination.md`: JSON output of `admin user list` is
  `{"data": [...], "nextPageToken": "..."}`; examples reading `.pagination` or
  `.pagination.next_page_token` should read `.nextPageToken`; without `--page-size` the API's
  default page size is used (not the `page_size` setting).
- `docs/api/wrapper.md` ("Admin Service API"): methods return SDK models/responses, search and
  list methods return one page, `create_group(name=, organizations=, attributes=,
  description=)`.
- `src/pltr/cli.py` (not docs, not mine): the `admin` group's help, "Admin operations for user,
  group, and organization management", could mention roles and markings.

### Not verified live

- No live Foundry stack was available; request and response shapes come from the SDK 1.111.0
  models and were checked against a real `FoundryClient` with faked HTTP.
- `Organization.replace` and `Marking.replace` clearing the optional fields they aren't sent
  (the reason `replace` now reads first) is inferred from their replace (PUT) semantics. If the
  API keeps omitted fields, the extra read is just redundant.
- `admin org replace --description ''` / `marking replace --description ''` send an empty
  description; whether Foundry stores it as empty or rejects it isn't verified.
- `Group.create` with an empty `attributes` map and `Marking.create` with an empty
  `initialMembers` list (no `--member`) are assumed to be accepted.
- Role IDs listed by `admin org available-roles` (core `Role.id`) are assumed to be accepted by
  `admin role get`/`role batch-get` (admin `Role`).
- `--include-deleted` defaulting to true when omitted, and the search semantics (case-insensitive
  prefix, deleted users excluded), come from the SDK docstrings.
