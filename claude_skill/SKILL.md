---
name: pltr-cli
description: Work with Palantir Foundry through the pltr CLI, which covers every Foundry Platform API endpoint. Datasets and files, SQL, ontologies and objects, actions, builds and schedules, folders, projects, spaces, permissions and markings, users and groups, models, streams, media sets, AIP agents and more. Use it when the user mentions Foundry, pltr, a Foundry RID (ri.*), datasets, ontology objects, builds or schedules.
---

# pltr: Palantir Foundry from the command line

pltr wraps the official Foundry Platform SDK (`foundry-platform-sdk`). It has
two kinds of commands:

- **Curated commands** (`pltr dataset`, `pltr sql`, `pltr ontology`,
  `pltr orchestration`, `pltr folder`, `pltr admin`, ...) are the polished
  path for common tasks, with friendly arguments and tables.
- **Generated commands** (`pltr api <namespace> <resource> <method>`) mirror
  the SDK one to one: one command per SDK method (390). Use them for
  anything the curated commands don't cover, or when you want the API's
  exact request and response shapes.

This skill needs a pltr release that has `pltr commands`. Check with
`pltr commands --help`; older releases lack the JSON contract described here.

## 1. Find the command; don't guess

pltr has more than 600 commands, so don't guess names or flags:

```bash
pltr commands search list dataset branches        # ranked, best first
pltr commands search Dataset.Branch.list          # by SDK method
pltr commands show dataset branches list --format json
pltr commands list api datasets                   # everything under a path
```

`search` matches names, descriptions and SDK methods, and ranks curated
commands above generated ones that match as well. `show` prints one command's
manifest entry:

- `usage`, `arguments` and `options` (flags, type, required, choices, default;
  `acceptsPath: true` when it takes a Compass path as well as a RID);
- `beta`, `destructive` and `paged`;
- `outputFormats` (`binary` means raw bytes);
- `sdkMethods` (the SDK method it calls, relative to `FoundryClient`);
- `generated` (a `pltr api` command) and `local` (makes no Foundry call).

An entry without `beta`/`destructive` hasn't recorded its metadata yet;
read its `--help` before running it. `pltr commands list --format json`
prints the whole manifest.

The `reference/` folder holds the same information as Markdown, one file per
command group, generated from the manifest. Start at
[reference/index.md](reference/index.md) and load only the file you need.

## 2. Authenticate (headless works)

pltr uses the first of these that applies:

1. `--profile NAME` on the command line;
2. the `PLTR_PROFILE` environment variable (a profile name);
3. the default profile, set up with `pltr configure configure`;
4. environment variables, when no profile is selected:
   - `FOUNDRY_HOST` and `FOUNDRY_TOKEN`, or
   - `FOUNDRY_HOST`, `FOUNDRY_CLIENT_ID` and `FOUNDRY_CLIENT_SECRET`
     (OAuth2 client credentials).

With environment variables nothing needs to be set up: no configuration
file and no keyring. A stored profile always wins over the variables.
Check what pltr will use with:

```bash
pltr verify --format json
```

Never print, log or echo tokens or client secrets.

## 3. Run with JSON and read the result

Pass `--format json`, or set `PLTR_FORMAT=json` once for the session.

- **stdout carries exactly one JSON document**: the SDK's own serialization,
  with Foundry API field names (camelCase) and no null fields. Single objects
  print as themselves. Lists use the API's paged shape,
  `{"data": [...], "nextPageToken": "..."}`. A command with no result (a
  delete, a grant) prints `null`.
- **Paged commands print one page.** Pass `nextPageToken` back with
  `--page-token`, or use `--max-pages N` or `--all`.
- **stderr carries JSON Lines only**: warnings look like
  `{"type": "warning", "message": "..."}`. On failure the last stderr line is
  the error object:
  `{"type": "not_found", "message": "...", "exitCode": 5, "statusCode": 404, "errorName": "...", "parameters": {...}}`.
- **Binary commands** (file content, Arrow or Parquet results, images)
  write raw bytes to `--output FILE` or to a pipe, never to a terminal.

| Exit | Meaning | What to do |
|---|---|---|
| 0 | success | |
| 1 | unexpected error, or "no" at a prompt | read the message; `PLTR_DEBUG=1` shows a traceback |
| 2 | usage error, or `--yes` required; `wrong_resource_type`: a path to the wrong kind of resource | fix the arguments (`pltr commands show ...`) |
| 3 | authentication | check credentials with `pltr verify` |
| 4 | permission denied (403) | the account lacks access; tell the user |
| 5 | not found (404); `path_not_found`: nothing at a path you gave | check the RID or path and that the account can see it |
| 6 | the API rejected the request (400, 422) | fix the input; see `errorName` and `parameters` |
| 7 | other API or network error (409, 429, 5xx, timeouts), or `invalid_response`: the API's response doesn't match the SDK's model or isn't JSON | retry later, or report it; for `invalid_response`, upgrade pltr: a retry won't help |
| 8 | the work failed (`work_failed`: a build, query or import you waited for) or a `pltr assert` check failed (`assertion_failed`) | read `parameters` (failed jobs) or the assert result on stdout |
| 9 | `--wait` timed out (`wait_timeout`); the work keeps running | run `suggestedCommand` to wait again |

### Errors that say how to recover

When pltr knows how to recover, the error object has a `hint` and often a
`suggestedCommand`. Read them before retrying, and don't retry blindly:

- `ObjectTypeNotFound`, `PropertiesNotFound`, `ActionTypeNotFound`,
  `LinkTypeNotFound`: the hint lists the closest API names;
- `wrong_resource_type`: you passed a RID or path of the wrong kind; for a
  folder, `suggestedCommand` lists it;
- `OpenTransactionAlreadyExists` (`conflict`): the hint names the open
  transaction and `suggestedCommand` aborts it. Aborting discards its
  uploads: ask the user unless you opened it yourself;
- `ApiUsageDenied` (`permission_denied`): the OAuth scope that's missing;
  tell the user;
- `<Operation>PermissionDenied`: the operation and resource;
  `suggestedCommand` shows who has roles on it;
- `auth_error` after HTTP 401: the token expired or was revoked; ask the user
  for a new one (`suggestedCommand` shows where it goes);
- `path_not_found`: what a Compass path looks like.

## 4. Safety rules

- **Destructive commands** (`destructive: true`: delete, remove, revoke,
  replace, reset, cancel, abort and similar) ask for confirmation. With
  `--format json`, or without a terminal, they never prompt: they fail with
  exit code 2 and change nothing unless you pass `--yes`.
- Pass `--yes` only for a change the user asked for, on resources they
  named. Show them the exact command first when you're unsure. Never loop a
  destructive command over a list you built yourself without confirming the
  list with the user.
- `--confirm` and `--force` (where they meant "skip the prompt") are
  deprecated aliases of `--yes`; use `--yes`.
- **Beta** commands start their help with `[beta]` and have `beta: true`.
  pltr passes `preview=true` for you, but beta endpoints can change or be
  turned off on a stack; say so when you rely on one.
- Prefer reading before writing: `get`/`list` the resource, then change it.

## 5. RIDs

Foundry's API addresses almost everything by RID (Resource Identifier), not by
name: `ri.<service>.<instance>.<type>.<id>`. For example:

- dataset: `ri.foundry.main.dataset.<uuid>`;
- space, project or folder: `ri.compass.main.folder.<uuid>`. The API can't
  list the root folder (`ri.compass.main.folder.0`); start from
  `pltr space list`.

**Paths work too.** Wherever a command takes the RID of a Compass resource
(dataset, folder, project, any resource, media set, connection, model, agent,
...), you can pass the resource's full path instead, starting with its space:
`pltr dataset get "/My Space/My Project/flights"`. pltr resolves it to the RID
before calling the API (one lookup for all the paths in a command) and fails
with `wrong_resource_type` if it's the wrong kind of resource. The API is still
RID-based: output shows RIDs, so save the RID for later calls. Spaces and the
root folder can't be looked up by path. Usage lines show such options as
`RID|PATH`, and the reference marks such arguments "(RID or path)".

Users and groups are identified by UUIDs, ontologies by RID or API name, and
object types by API name. Don't construct RIDs; get them from the user, from
a path, or from command output:

```bash
pltr resource get-by-path "/My Space/My Project/flights" --format json   # path -> RID
pltr resource search flights --folder-rid ri.compass.main.folder.<uuid> --format json
pltr space list --format json
pltr project list --format json
pltr folder list ri.compass.main.folder.<uuid> --format json               # a space, project or folder
pltr ontology list --format json
pltr admin user search jane --format json                                  # user IDs
```

## 6. Curated command or `pltr api`?

1. Search first. If a curated command does the job, use it: its arguments
   are friendlier and its help explains the domain.
2. Use `pltr api ...` when no curated command covers the endpoint, or when
   you need an option the curated command doesn't expose.
3. `pltr api` arguments are the endpoint's path parameters. Options taking
   JSON accept the Foundry API's own shape (camelCase), inline, as
   `@file.json` or as `@-` for stdin, and the SDK validates the value before
   anything is sent.

## 6a. The verify loop: trigger with `--wait`, then `pltr assert`

After you start a build, a schedule run, an import or a SQL query, don't poll
by hand and don't stop checking early. Add `--wait` (and `--timeout`
seconds; default 600, or 300 for SQL): pltr returns once the work finished,
with exit 0 and the final state, exit 8 if it failed, or exit 9 if it's still
running (then run the error's `suggestedCommand`). Then verify the output
with `pltr assert`, which exits 8 when a check fails:

```bash
pltr orchestration builds create '{"type": "manual", "targetRids": ["ri.foundry.main.dataset.abc"]}' --wait --format json
pltr assert dataset ri.foundry.main.dataset.abc --min-rows 1 --updated-within 1h --format json
pltr assert build ri.foundry.main.build.abc --succeeded
pltr assert objects my-ontology Employee --min-count 1
```

`--schema expected.json` compares a dataset's columns with the output of
`pltr dataset schema get --format json`. To check an ontology action without
applying it, use `pltr ontology action-validate`.

## 6b. Writing app code: `--emit-code`

When you write code that calls Foundry (an app, a pipeline, a script), first
get the call working with pltr, then add `--emit-code` to the same command:
it prints the foundry-platform-sdk Python code for that call, with the same
arguments, instead of running it. Use it instead of guessing SDK parameter
names, model classes or pagination:

```bash
pltr ontology object-search my-ontology Employee --where '{"type": "eq", "field": "dept", "value": "R&D"}' --emit-code
pltr api datasets dataset read-table <dataset-rid> --api-format ARROW --emit-code
```

The snippet reads `FOUNDRY_HOST` and `FOUNDRY_TOKEN` (and any secret
argument, such as connection secrets) from the environment, looks up any
Compass path you gave, and pages the SDK's way: read its comments. Nothing runs, so
it's safe on destructive commands. A command that makes several calls (or no
Foundry call) fails with `emit_code_unsupported` (exit 2): use `pltr commands
show <command>` for its SDK methods and `pltr api ... --emit-code` for each.

## 7. Workflows

**Inspect a dataset and query it with SQL**

```bash
pltr resource get-by-path "/My Space/My Project/flights" --format json
pltr dataset get ri.foundry.main.dataset.<id> --format json
pltr dataset files list ri.foundry.main.dataset.<id> --format json
pltr sql execute 'SELECT origin, COUNT(*) AS n FROM `ri.foundry.main.dataset.<id>` GROUP BY origin' --format json
```

**Build a dataset and follow the build**

```bash
pltr orchestration builds create '{"type": "manual", "targetRids": ["ri.foundry.main.dataset.<id>"]}' --branch master --format json
pltr orchestration builds get ri.foundry.main.build.<id> --format json
pltr orchestration builds jobs ri.foundry.main.build.<id> --format json
```

**Search ontology objects** with Foundry's typed query (`SearchJsonQueryV2`):

```bash
pltr ontology object-search my-ontology Aircraft \
  --where '{"type": "eq", "field": "status", "value": "ACTIVE"}' \
  --properties tailNumber,status --format json
```

`pltr api ontologies ontology-object search` takes the endpoint's request
exactly as Foundry's API docs describe it, for options the curated command
doesn't have.

**Grant access to a project**

```bash
pltr admin user search jane --format json                      # find the user ID
pltr resource-role list ri.compass.main.folder.<id> --format json   # role IDs in use
pltr resource-role grant ri.compass.main.folder.<id> --role <role-id> --principal-id <user-uuid>
```

Role IDs come from the role set of the project's space (for example
`compass:manage` is Owner in the default role set).

More: [workflows/](workflows/) has longer workflows for data exploration,
pipelines and permissions.

## Getting help

```bash
pltr commands search <words>      # find a command
pltr commands show <command>      # everything about one command
pltr <group> --help               # a group's commands
```
