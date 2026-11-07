### Breaking

- **`project`, `resource`, `resource-role` and `cp` follow the output
  contract.** `--format json` prints the SDK's own serialization: Foundry API
  field names (camelCase), no null fields, lists as `{"data": [...],
  "nextPageToken": "..."}`. Per command:
  - `project create`/`get`/`update`/`create-from-template`: the `Project`
    model (`displayName`, `spaceRid`, `createdTime`, `updatedBy`,
    `resourceLevelRoleGrantsAllowed`, ...). The invented `"type": "project"`
    key and the `modified_by`/`modified_time` keys are gone.
  - `project list`: `{"data": [...]}` of the projects' `Resource` metadata
    (with `nextPageToken` when `--space-rid` is given).
  - `project list-orgs`: `{"data": ["<organization RID>", ...]}`. It used to
    print objects whose `display_name` and `description` were always null.
  - `resource get`/`get-by-path`: the `Resource` model. The always-null
    `name`, `folder_rid`, `size_bytes` and `modified_*` keys are gone;
    `parentFolderRid`, `projectRid` and `spaceRid` are new.
  - `resource list` and `resource search`: `{"data": [...]}` of `Resource`
    models (`list` adds `nextPageToken`).
  - `resource batch-get`: the API response, `{"data": {"<RID>": {...}}}`.
    `resource batch-get-by-path`: `{"data": [...]}`.
  - `resource list-markings`: `{"data": ["<marking ID>", ...]}`.
  - `resource access-requirements`: the API response, `{"organizations":
    [{"markingId", "organizationRid", "isDirectlyApplied"}], "markings":
    [{"markingId", "isDirectlyApplied"}]}`.
  - `resource-role list`: `{"data": [{"resourceRolePrincipal": {...},
    "roleId": "..."}]}`.
  - Commands whose API call returns no body (`project delete`, `add-orgs`,
    `remove-orgs`; `resource delete`, `restore`, `permanently-delete`,
    `add-markings`, `remove-markings`; `resource-role grant`, `revoke`) now
    take `--format` and print `null` in JSON mode, nothing in table/CSV mode.
  - `cp` prints the resources it created (`{"data": [...]}` of the API's
    `Folder` and `Dataset` objects; a table or CSV otherwise). Its progress
    messages and summary moved from stdout to stderr.
- **Exit codes**: errors used to exit with 1. They now exit with 2 (usage), 3
  (authentication), 4 (permission denied), 5 (not found), 6 (validation) or
  7 (other API or network error), with a structured error on stderr.
- **List commands fetch one page by default**: `project list --space-rid`,
  `project list-orgs`, `resource list` and `resource list-markings` used to
  fetch every page (as does the now working `resource-role list`). Use
  `--all`, `--max-pages N`, or `--page-token` with the `nextPageToken` of an
  earlier response.
- **Confirmation**: `project remove-orgs` and `resource remove-markings` now
  ask for confirmation. `project delete`, `resource delete`,
  `resource permanently-delete` and `resource-role revoke` no longer prompt
  when stdin is not a terminal. Without `--yes`/`-y` these commands exit
  with code 2. Prompts are written to stderr.
- **`-f` on `resource delete` and `resource permanently-delete` is now
  `--format`**; it used to be `--force`. `--force` still works as a hidden,
  deprecated alias of `--yes` (see Deprecated).
- **`resource list` and `resource search` no longer accept `-o`**, which used
  to be the short flag of `--format`. `-f` stays `--folder-rid` there, so
  `--format` and `--output` have no short flags on these two commands; an old
  `-o json` now fails with a usage error instead of being read as
  `--output json`.
- **`resource list`/`search --type` takes the API's resource type names**
  (`FOUNDRY_DATASET`, `COMPASS_FOLDER`, ...; case-insensitive, with `dataset`
  and `folder` as short names). An unknown type is a usage error (exit 2).
  Before, the filter compared against the wrong names, so `--type dataset`
  matched nothing.
- **`resource-role grant`/`revoke` take a user or group ID** (a UUID) with
  `--principal-id`, and a role ID with `--role`. Usernames and group names
  are rejected with exit code 2. (Both commands always failed before; see
  Fixed.)
- **`project delete` moves the project to the trash** with
  `Resource.delete`, after checking that the RID is a project. Restore it
  with `pltr resource restore`. (It always failed before.)
- **`project list` without `--space-rid` rejects `--page-token` and
  `--max-pages`** (exit 2): it reads every page of every space.
- **`resource search`** returns `{"data": [...]}`, stops after
  `--max-folders` folders (default 1000) with a warning that the results may
  be incomplete (it used to fail and discard what it had found), and an
  empty query is a usage error.
- **`cp` exits with the error of the first failed item** when copying a
  folder and some items fail (it used to exit 0). It still copies the other
  items unless `--fail-fast`, and prints what it created.
- **`--format`/`-f` is validated** on these commands: only table, json and
  csv are accepted (case-insensitive).
- **Table and CSV columns changed** to real model fields (see Fixed).

### Added

- `--page-token`, `--max-pages` and `--all` on `project list` (with
  `--space-rid`), `project list-orgs`, `resource list`,
  `resource list-markings` and `resource-role list`, next to their existing
  `--page-size`.
- `--output`/`-o` on `project create`, `project update` and `cp`; `-o` for
  `--output` on `project list-orgs`; `--output` (long only) on
  `project create-from-template`, where `-o` is `--org`.
- `-p` as the short form of `--profile` on every `project`, `resource` and
  `cp` command and on `resource-role list`. `resource-role grant`/`revoke`
  keep `-p` for `--principal-id`.
- `project create --owner-role` (the role granted to the owner, default
  `compass:manage`) and `--default-role` (repeatable).
- `project create-from-template --default-role` (repeatable).
- `resource-role grant`/`revoke --everyone`: grant or revoke a role for the
  Everyone principal.
- `resource-role list --include-inherited`: also list inherited roles.
- `resource-role list --principal-type` accepts `EVERYONE`.
- `resource search --limit` (stop after N matches) and `--max-folders`.
- `resource batch-get` and `batch-get-by-path` warn about RIDs and paths that
  weren't found or can't be read.
- `[beta]` label on `project update`: it calls the beta `Project.replace`
  endpoint, always with `preview=true`.

### Changed

- `project update` reads the project and sends back the field you don't
  change. `Project.replace` clears an omitted description, so
  `project update --name X` used to erase the description.
- `project create` looks up the calling user with `admin.User.get_current`
  for the default owner, and `--owner-type` only accepts USER or GROUP; it
  needs `--owner-id`.
- `project create-from-template --var` is optional (a template may have no
  variables).
- `project list` without `--space-rid` lists the projects of every space
  (every page of `Space.list` and of each space's children).
- `resource-role list --principal-type` filters the fetched pages locally;
  the API has no such filter.
- `resource list` help says it lists the root folder when `--folder-rid` is
  not given, and that `--type` filters each page locally.
- `resource search` help says it scans folders (the Foundry API has no search
  endpoint), one request per page per folder, and matches display names,
  paths, descriptions, RIDs and types.
- `cp --dry-run` prints the source resources that would be copied. Skipped
  items are warnings (JSON lines in JSON mode). A partly copied dataset is
  removed through the dataset service after a failure.
- `cp`'s file upload passes explicit keywords to `Dataset.File.upload`
  (a transaction or a branch, never both).

### Deprecated

- `project delete --confirm` and `resource-role revoke --confirm`: hidden
  aliases of `--yes` that print a deprecation warning.
- `resource delete --force` and `resource permanently-delete --force`:
  hidden aliases of `--yes` that print a deprecation warning. Their `-f`
  short flag was dropped (it is `--format` now).
- `resource-role grant`/`revoke --principal-type`/`-t`: hidden, ignored, and
  prints a deprecation warning. Granting and revoking only need the
  principal's ID.
- `resource search --page-size`: hidden alias of `--limit` that prints a
  deprecation warning.
- `cp --debug`: hidden; prints a deprecation warning. Set `PLTR_DEBUG=1` to
  see tracebacks.

### Removed

- `resource get-metadata`: the SDK has no `Resource.get_metadata`, so the
  command always failed. Use `pltr resource get`.
- `resource-role get-principal-roles`: the SDK has no endpoint that lists a
  principal's roles across resources; the command always failed.
- `resource-role get-available-roles`: the SDK has no endpoint that lists the
  roles available on a resource; the command always failed. `pltr
  resource-role list` shows the role IDs in use on a resource.
- Unused `ResourceRoleService.bulk_grant_roles`/`bulk_revoke_roles`, which
  called SDK methods that don't exist (#182).

### Fixed

- `resource-role grant`, `revoke` and `list` always failed: they called
  `filesystem.ResourceRole`, which doesn't exist (#182). They now call
  `Resource.Role.add`, `remove` and `list`.
- `project delete` always failed: `Project.delete` doesn't exist (#182).
- `resource batch-get` and `batch-get-by-path` always failed: they read a
  `resources` field; the responses have `data`.
- `project list` filtered on a resource type (`PROJECT`) and a RID prefix
  (`ri.compass.main.project.`) that real projects don't have, so it most
  likely never listed anything. It now keeps the children of a space whose
  `projectRid` is their own RID.
- Output that read fields the SDK models don't have (#183) and printed
  `N/A` or null: `resource get`/`get-by-path`/`list`/`search` (name, folder
  RID, size), `project list-orgs` (organization names and descriptions: the
  API returns RIDs only), `resource list-markings` (marking names and
  categories: the API returns IDs only), `resource access-requirements`
  (organization names) and `resource-role list` (granted by/time, expiry).
- No more `preview=` on GA endpoints, so the SDK warning is gone (#184):
  `project get`/`list`/`update`/`add-orgs`/`remove-orgs`/`list-orgs`/
  `create`/`create-from-template` and every `resource` command.
- `project create` called `Project.create` through signature sniffing with a
  dead `body=` branch; it is one explicit call now.
- `cp` printed its progress to stdout, counted a `--fail-fast` failure once
  per folder level, and exited 0 when items failed.

### Docs to update

- `README.md` lines 102-107 and 227-229: `pltr project create "My Project"
  ri.compass.main.space.123` needs `--space-rid`; `pltr resource-role grant
  <rid> user123 User viewer` must be `pltr resource-role grant <rid>
  --principal-id <user-or-group-id> --role <role-id>`. Project and space RIDs
  look like `ri.compass.main.folder.<id>`, not `ri.compass.main.space/project`.
- `docs/user-guide/commands.md`:
  - `pltr cp` (line 439): JSON/stdout output, `--dry-run` output, exit code on
    partial failure, `--debug` deprecated.
  - Project commands (line 1584): `create` takes `--space-rid` (not a
    positional SPACE_RID), new `--owner-role`/`--default-role`; `update` is
    `[beta]`; `delete` moves to the trash and needs `--yes` when not
    interactive; `add-orgs`/`remove-orgs`/`list-orgs`/`create-from-template`
    are missing.
  - Resource commands (line 1683): `--resource-type` doesn't exist (it is
    `--type`/`-t` with API type names); document `search` as a folder scan
    with `--limit`/`--max-folders`; `get-metadata` was removed; trash,
    marking and access-requirement commands are missing.
  - Resource role commands (line 1769): `grant`/`revoke` take
    `--principal-id`/`--everyone` and `--role`, not positional
    PRINCIPAL_ID PRINCIPAL_TYPE ROLE_NAME; remove `get-principal-roles`,
    `bulk-grant`, `bulk-revoke` and `available-roles` (none exist); add
    `list --include-inherited`.
  - Paging flags and the JSON paged shape for the list commands.
- `docs/user-guide/workflows.md` lines 283-392: same `project create`,
  `resource-role` and `--resource-type` fixes; drop `resource get-metadata`,
  `resource-role bulk-grant`, `available-roles` and `get-principal-roles`.
- `docs/examples/gallery.md`: the `pltr cp` anchor link may change with the
  commands.md heading.
- `claude_skill/reference/filesystem-commands.md` (project, resource and
  resource-role sections), `claude_skill/workflows/permission-management.md`
  and `claude_skill/reference/dataset-commands.md` (cp): the same changes;
  `project update` uses `--name`, not `--display-name`.
- `src/pltr/cli.py`: register `cp` without `help=` so `pltr cp --help` shows
  the command's docstring (output, dry-run and partial-failure behaviour).
- `CHANGELOG.md`: fold this fragment into the release notes.

### Not verified live

- `project delete` assumes `Resource.delete` accepts project RIDs. The SDK
  treats projects as resources (`Resource.get` rejects only spaces and the
  root folder; `Resource.projectRid` is documented as the project's own RID
  for a project; there is a `TrashingSpaceNotSupported` error but no project
  equivalent), but this wasn't tried against a stack.
- `project list` assumes the children of a space are its projects, returned
  as `Resource`s whose `projectRid` is their own RID.
- `project create` grants `compass:manage` to the owner by default, as
  earlier releases did; spaces with a custom role set may need
  `--owner-role`. The help's example role ID (`compass:manage`, Owner)
  assumes Foundry's default role set.
- `resource list` and `resource search` without `--folder-rid` list the root
  folder (`ri.compass.main.folder.0`), as earlier releases did. Whether the
  API lists the root folder's children (spaces) as resources wasn't checked.
- `resource-role list --include-inherited` sends `includeInherited=true`; what
  the API counts as inherited wasn't checked.
- `cp`'s dataset steps run through the dataset service's compatibility
  methods; the request sequence of a dataset copy (create, schema, list
  files, download, upload, commit) wasn't run against a stack.
